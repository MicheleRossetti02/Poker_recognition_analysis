import { User, Wifi, WifiOff } from 'lucide-react';
import { usePokerWebSocket } from '../hooks/usePokerWebSocket';
import Card from './Card';
import GTOPanel from './GTOPanel';

/**
 * PokerTableLive - Real-time poker table visualization
 * Connects to vision bot WebSocket and displays live game state
 */
export default function PokerTableLive() {
    const { gameState, connected, error } = usePokerWebSocket();

    // Helper to get seat position on oval table
    const getSeatPosition = (angle) => {
        const radiusX = 42;
        const radiusY = 38;
        const rad = (angle * Math.PI) / 180;
        return {
            left: `${50 + radiusX * Math.cos(rad)}%`,
            top: `${50 + radiusY * Math.sin(rad)}%`,
        };
    };

    // Position angles for 9-max table
    const POSITIONS = {
        'BTN': 270,
        'SB': 230,
        'BB': 190,
        'UTG': 150,
        'UTG+1': 110,
        'MP': 70,
        'CO': 350,
        'HJ': 310,
        'UTG+2': 30
    };

    // Get GTO suggestion color
    const getGTOColor = (action) => {
        if (!action) return 'gray';
        const upper = action.toUpperCase();
        if (upper.includes('RAISE') || upper.includes('BET')) return 'green';
        if (upper.includes('CALL')) return 'yellow';
        if (upper.includes('FOLD')) return 'red';
        return 'gray';
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-4">
            {/* Header with connection status */}
            <header className="text-center mb-6">
                <div className="flex items-center justify-center gap-3 mb-2">
                    {connected ? (
                        <Wifi className="w-6 h-6 text-green-400 animate-pulse" />
                    ) : (
                        <WifiOff className="w-6 h-6 text-red-400" />
                    )}
                    <h1 className="text-4xl font-bold text-white">
                        🃏 Live GTO Poker Dashboard
                    </h1>
                </div>
                <p className="text-gray-400">
                    {connected ? 'Connected to vision bot' : 'Connecting...'}
                </p>
                {error && (
                    <p className="text-red-400 text-sm mt-1">Error: {error}</p>
                )}
            </header>

            {/* Game Info Bar */}
            {gameState && (
                <div className="flex gap-4 mb-4 p-3 bg-gray-800/50 rounded-xl backdrop-blur-sm text-white text-sm">
                    <div>Hand <span className="font-bold">#{gameState.hand_id}</span></div>
                    <div>Street: <span className="font-bold">{gameState.street}</span></div>
                    <div>Pot: <span className="font-bold">{gameState.pot?.toFixed(1)}BB</span></div>
                    <div>Board: <span className="font-mono">{gameState.board?.join(' ') || 'None'}</span></div>
                </div>
            )}

            {/* Main Table Area */}
            <div className="relative w-full max-w-5xl aspect-[16/10]">
                {/* Poker Table (Green Oval) */}
                <div className="absolute inset-8 rounded-[50%] bg-gradient-to-br from-emerald-800 to-green-900 shadow-2xl border-8 border-amber-900">
                    {/* Table felt texture */}
                    <div className="absolute inset-0 rounded-[50%] bg-[radial-gradient(ellipse_at_center,_transparent_0%,_rgba(0,0,0,0.3)_100%)]"></div>

                    {/* Table rail */}
                    <div className="absolute -inset-2 rounded-[50%] border-4 border-amber-800 pointer-events-none"></div>

                    {/* Center - GTO Panel */}
                    <div className="absolute inset-0 flex items-center justify-center p-12">
                        <div className="w-full max-w-2xl">
                            <GTOPanel
                                suggestion={gameState?.gto_suggestion?.action || 'Waiting for hand...'}
                                color={getGTOColor(gameState?.gto_suggestion?.action)}
                            />
                        </div>
                    </div>
                </div>

                {/* Player Seats */}
                {gameState?.players?.map((player, idx) => {
                    const position = getSeatPosition(POSITIONS[player.position] || 270);
                    const isHero = player.position === gameState.hero?.position;
                    const isDealer = player.is_dealer;

                    return (
                        <div
                            key={`${player.name}-${idx}`}
                            className="absolute transform -translate-x-1/2 -translate-y-1/2"
                            style={position}
                        >
                            {/* Seat circle */}
                            <div className={`
                w-20 h-20 md:w-24 md:h-24 rounded-full flex flex-col items-center justify-center
                transition-all duration-300
                ${isHero
                                    ? 'bg-gradient-to-br from-yellow-600 to-amber-700 ring-4 ring-yellow-400 shadow-lg shadow-yellow-500/30'
                                    : player.status === 'Folded'
                                        ? 'bg-gray-700 opacity-50'
                                        : 'bg-gray-800 ring-2 ring-gray-600'
                                }
              `}>
                                {/* Position label */}
                                <span className={`text-xs font-bold ${isHero ? 'text-yellow-100' : 'text-gray-400'}`}>
                                    {player.position}
                                    {isDealer && ' 🔘'}
                                </span>

                                {/* Player icon or cards */}
                                {isHero && gameState.hero?.cards?.length === 2 ? (
                                    <div className="flex -space-x-1 mt-1 scale-75">
                                        {gameState.hero.cards.map((card, i) => (
                                            <Card key={i} card={card} small />
                                        ))}
                                    </div>
                                ) : (
                                    <User className={`w-5 h-5 ${isHero ? 'text-yellow-200' : 'text-gray-500'}`} />
                                )}

                                {/* Stack size */}
                                <span className="text-xs font-semibold text-white mt-1">
                                    {player.stack?.toFixed(1)}BB
                                </span>
                            </div>

                            {/* Hero label */}
                            {isHero && (
                                <div className="absolute -bottom-6 left-1/2 transform -translate-x-1/2 font-bold text-xs text-yellow-400">
                                    {player.name}
                                </div>
                            )}

                            {/* Last action */}
                            {player.last_action && player.last_action !== 'Waiting' && (
                                <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 bg-gray-900/90 px-2 py-1 rounded text-xs text-white whitespace-nowrap">
                                    {player.last_action}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Debug info (optional) */}
            {gameState && (
                <div className="mt-4 text-xs text-gray-500 text-center">
                    Last update: {new Date(gameState.timestamp).toLocaleTimeString()}
                </div>
            )}
        </div>
    );
}
