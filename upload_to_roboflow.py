#!/usr/bin/env python3
"""
Intelligent Roboflow Upload Script
===================================
Upload automatico intelligente con:
- Import credenziali da train.py
- Multi-threading per performance
- Retry logic (3 tentativi)
- Batch tagging con session name
- Logging dettagliato

USO:
    # Upload sessione specifica
    python upload_to_roboflow.py dataset/raw/session_20260117_133527/
    
    # Upload tutte le sessioni
    python upload_to_roboflow.py dataset/raw/ --recursive
    
    # Dry run (test senza upload)
    python upload_to_roboflow.py dataset/raw/session_20260117_133527/ --dry-run

REQUISITI:
    pip install roboflow tqdm
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ============================================================================
# IMPORT CREDENZIALI DA train.py
# ============================================================================
def import_credentials_from_train() -> Tuple[str, str, str]:
    """
    Importa credenziali Roboflow da train.py invece di hardcodare.
    
    Returns:
        Tuple (api_key, workspace, project)
    
    Raises:
        ImportError: Se train.py non esiste o manca le costanti
    """
    try:
        # Import dinamico train.py
        import importlib.util
        spec = importlib.util.spec_from_file_location("train", "train.py")
        if spec is None or spec.loader is None:
            raise ImportError("train.py non trovato")
        
        train_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(train_module)
        
        # Estrai costanti
        api_key = getattr(train_module, 'ROBOFLOW_API_KEY', None)
        workspace = getattr(train_module, 'WORKSPACE', None)
        project = getattr(train_module, 'PROJECT', None)
        
        if not all([api_key, workspace, project]):
            raise ImportError("Costanti mancanti in train.py")
        
        return api_key, workspace, project
    
    except Exception as e:
        print(f"❌ Errore import credenziali da train.py: {e}")
        print("\n💡 Assicurati che train.py contenga:")
        print("   ROBOFLOW_API_KEY = '...'")
        print("   WORKSPACE = '...'")
        print("   PROJECT = '...'")
        sys.exit(1)


# ============================================================================
# CONFIGURAZIONE
# ============================================================================
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # Secondi
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png']
MAX_WORKERS = 4  # Thread pool size


class UploadStats:
    """Thread-safe statistics tracker."""
    
    def __init__(self):
        self._lock = Lock()
        self.total_files = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        self.failed_files: List[str] = []
    
    def increment_success(self):
        with self._lock:
            self.successful += 1
    
    def increment_failure(self, filename: str):
        with self._lock:
            self.failed += 1
            self.failed_files.append(filename)
    
    def increment_skip(self):
        with self._lock:
            self.skipped += 1
    
    def set_total(self, count: int):
        with self._lock:
            self.total_files = count
    
    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_files": self.total_files,
                "successful": self.successful,
                "failed": self.failed,
                "skipped": self.skipped,
                "success_rate": (self.successful / self.total_files * 100 
                                if self.total_files > 0 else 0),
                "failed_files": self.failed_files.copy()
            }


class RoboflowUploader:
    """Upload intelligente a Roboflow con multi-threading e retry."""
    
    def __init__(self, api_key: str, workspace: str, project: str,
                 batch_name: Optional[str] = None, dry_run: bool = False):
        """
        Inizializza uploader.
        
        Args:
            api_key: Roboflow API key
            workspace: Nome workspace
            project: Nome progetto
            batch_name: Nome batch/tag per organizzazione
            dry_run: Se True, simula upload senza eseguirli
        """
        self.api_key = api_key
        self.workspace_name = workspace
        self.project_name = project
        self.batch_name = batch_name
        self.dry_run = dry_run
        
        self.rf = None
        self.project = None
        
        if not dry_run:
            self._initialize()
    
    def _initialize(self):
        """Inizializza connessione Roboflow."""
        try:
            from roboflow import Roboflow
            
            self.rf = Roboflow(api_key=self.api_key)
            workspace = self.rf.workspace(self.workspace_name)
            self.project = workspace.project(self.project_name)
            
            print(f"✅ Connesso a Roboflow:")
            print(f"   Workspace: {self.workspace_name}")
            print(f"   Project: {self.project_name}")
            if self.batch_name:
                print(f"   Batch: {self.batch_name}")
        
        except ImportError:
            print("❌ Roboflow library non installata")
            print("   pip install roboflow")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Errore connessione Roboflow: {e}")
            sys.exit(1)
    
    def upload_single_image(self, image_path: Path, retry_count: int = 0) -> str:
        """
        Upload singola immagine con retry logic.
        
        Args:
            image_path: Path dell'immagine
            retry_count: Tentativo corrente (per recursione)
        
        Returns:
            'success', 'skip', o 'fail'
        """
        if self.dry_run:
            time.sleep(0.02)  # Simula latenza
            return 'success'
        
        try:
            # Upload con batch tag se specificato
            upload_params = {
                "image_path": str(image_path),
                "num_retry_uploads": 0  # Gestiamo noi i retry
            }
            
            if self.batch_name:
                upload_params["batch_name"] = self.batch_name
            
            self.project.upload(**upload_params)
            return 'success'
        
        except Exception as e:
            error_msg = str(e).lower()
            
            # Duplicate - non è errore, skippiamo
            if "duplicate" in error_msg or "already exists" in error_msg:
                return 'skip'
            
            # Rate limit - attendi e riprova
            if "rate limit" in error_msg or "429" in error_msg:
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF[retry_count] * 2
                    time.sleep(wait_time)
                    return self.upload_single_image(image_path, retry_count + 1)
                return 'fail'
            
            # Altri errori - retry con backoff
            if retry_count < MAX_RETRIES:
                wait_time = RETRY_BACKOFF[retry_count]
                time.sleep(wait_time)
                return self.upload_single_image(image_path, retry_count + 1)
            
            return 'fail'


def find_images(directory: Path, recursive: bool = False) -> List[Path]:
    """
    Trova tutte le immagini in una directory.
    
    Args:
        directory: Directory da scansionare
        recursive: Se True, scansiona anche subdirectory
    
    Returns:
        Lista di path alle immagini
    """
    images = []
    
    if recursive:
        # Scansione ricorsiva
        for ext in SUPPORTED_EXTENSIONS:
            images.extend(directory.glob(f"**/*{ext}"))
    else:
        # Solo directory corrente
        for ext in SUPPORTED_EXTENSIONS:
            images.extend(directory.glob(f"*{ext}"))
    
    return sorted(images)


def extract_batch_name(path: Path) -> Optional[str]:
    """
    Estrae il nome batch dalla path (es. session_20260117_133527).
    
    Args:
        path: Path della directory o file
    
    Returns:
        Nome batch se trovato, None altrimenti
    """
    # Cerca session_YYYYMMDD_HHMMSS nella path
    for part in path.parts:
        if part.startswith("session_"):
            return part
    
    return None


def upload_worker(uploader: RoboflowUploader, image_path: Path, 
                 stats: UploadStats, verbose: bool = True) -> None:
    """
    Worker function per upload in thread pool.
    
    Args:
        uploader: Istanza RoboflowUploader
        image_path: Path immagine da uploadare
        stats: Stats tracker condiviso
        verbose: Se True, stampa output dettagliato
    """
    result = uploader.upload_single_image(image_path)
    
    if result == 'success':
        stats.increment_success()
        if verbose:
            print(f"   ✅ {image_path.name}")
    elif result == 'skip':
        stats.increment_skip()
        if verbose:
            print(f"   ⏭️  {image_path.name} (duplicato)")
    else:
        stats.increment_failure(image_path.name)
        if verbose:
            print(f"   ❌ {image_path.name} (fallito dopo {MAX_RETRIES} retry)")


def main():
    parser = argparse.ArgumentParser(
        description="Upload intelligente a Roboflow con multi-threading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  %(prog)s dataset/raw/session_20260117_133527/
  %(prog)s dataset/raw/ --recursive
  %(prog)s dataset/raw/session_20260117_133527/ --dry-run --workers 8
        """
    )
    
    parser.add_argument("directory", type=str,
                       help="Directory contenente immagini da uploadare")
    parser.add_argument("--recursive", "-r", action="store_true",
                       help="Scansiona ricorsivamente subdirectory")
    parser.add_argument("--batch-name", "-b", type=str,
                       help="Nome batch/tag (default: auto-detect da session_*)")
    parser.add_argument("--workers", "-w", type=int, default=MAX_WORKERS,
                       help=f"Numero thread pool (default: {MAX_WORKERS})")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simula upload senza eseguirli")
    parser.add_argument("--verbose", "-v", action="store_true", default=True,
                       help="Output verboso per ogni file")
    
    args = parser.parse_args()
    
    # Verifica directory
    directory = Path(args.directory)
    if not directory.exists():
        print(f"❌ Directory non trovata: {directory}")
        sys.exit(1)
    
    # Banner
    print("=" * 70)
    print("📤 ROBOFLOW UPLOAD - Intelligent Multi-threaded")
    print("=" * 70)
    
    # Import credenziali da train.py
    print("\n🔐 Importando credenziali da train.py...")
    api_key, workspace, project = import_credentials_from_train()
    print(f"   ✅ API Key: {api_key[:10]}...")
    print(f"   ✅ Workspace: {workspace}")
    print(f"   ✅ Project: {project}")
    
    # Trova immagini
    print(f"\n📁 Scansionando {directory}...")
    images = find_images(directory, args.recursive)
    
    if not images:
        print(f"⚠️  Nessuna immagine trovata in {directory}")
        sys.exit(0)
    
    print(f"   Trovate {len(images)} immagini")
    
    # Auto-detect batch name
    batch_name = args.batch_name
    if not batch_name:
        batch_name = extract_batch_name(directory)
        if batch_name:
            print(f"   📦 Auto-detected batch: {batch_name}")
    
    # Inizializza uploader
    uploader = RoboflowUploader(
        api_key=api_key,
        workspace=workspace,
        project=project,
        batch_name=batch_name,
        dry_run=args.dry_run
    )
    
    # Stats tracker
    stats = UploadStats()
    stats.set_total(len(images))
    
    # Upload con multi-threading
    print(f"\n📤 Uploading {len(images)} immagini ({args.workers} threads)...")
    if args.dry_run:
        print("   🔍 DRY RUN - Nessun upload reale\n")
    
    start_time = time.time()
    
    try:
        from tqdm import tqdm
        use_tqdm = True
    except ImportError:
        use_tqdm = False
        print("   (installa tqdm per progress bar: pip install tqdm)\n")
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        
        for image_path in images:
            future = executor.submit(
                upload_worker,
                uploader,
                image_path,
                stats,
                args.verbose and not use_tqdm
            )
            futures.append(future)
        
        # Progress tracking
        if use_tqdm:
            with tqdm(total=len(futures), desc="Upload", unit="img") as pbar:
                for future in as_completed(futures):
                    future.result()  # Wait completion
                    pbar.update(1)
        else:
            for future in as_completed(futures):
                future.result()
    
    duration = time.time() - start_time
    
    # Report finale
    summary = stats.get_summary()
    
    print("\n" + "=" * 70)
    print("📊 UPLOAD REPORT")
    print("=" * 70)
    print(f"\n⏱️  Durata: {duration:.1f}s")
    print(f"   Throughput: {len(images) / duration:.1f} img/s\n")
    print(f"📈 Statistiche:")
    print(f"   Totale: {summary['total_files']}")
    print(f"   ✅ Successi: {summary['successful']}")
    print(f"   ❌ Falliti: {summary['failed']}")
    print(f"   ⏭️  Skipped: {summary['skipped']}")
    print(f"   Success rate: {summary['success_rate']:.1f}%")
    
    if summary['failed_files']:
        print(f"\n⚠️  File falliti:")
        for filename in summary['failed_files'][:10]:
            print(f"   - {filename}")
        if len(summary['failed_files']) > 10:
            print(f"   ... e altri {len(summary['failed_files']) - 10}")
    
    # Salva report JSON
    report = {
        "upload_timestamp": datetime.now().isoformat(),
        "directory": str(directory),
        "batch_name": batch_name,
        "duration_seconds": round(duration, 2),
        "throughput_img_per_sec": round(len(images) / duration, 2),
        "workers": args.workers,
        "dry_run": args.dry_run,
        **summary
    }
    
    report_path = directory / f"upload_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Report salvato: {report_path}")
    print("=" * 70)
    
    if not args.dry_run:
        print("\n📝 Prossimi passi:")
        print("   1. Verifica immagini su Roboflow dashboard")
        print(f"   2. Filtra per batch: {batch_name}")
        print("   3. Inizia annotazione")
        print("   4. Versiona dataset quando pronto")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
