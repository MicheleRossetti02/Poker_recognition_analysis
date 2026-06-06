import { useState, useEffect, useRef } from 'react';

/**
 * WebSocket hook for real-time game state
 * Connects to poker vision bot WebSocket server
 */
export function usePokerWebSocket(url = 'ws://localhost:8765') {
    const [gameState, setGameState] = useState(null);
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);

    useEffect(() => {
        let mounted = true;

        function connect() {
            try {
                console.log(`🔌 Connecting to ${url}...`);
                const ws = new WebSocket(url);

                ws.onopen = () => {
                    if (mounted) {
                        console.log('✅ WebSocket connected');
                        setConnected(true);
                        setError(null);
                    }
                };

                ws.onmessage = (event) => {
                    if (mounted) {
                        try {
                            const data = JSON.parse(event.data);
                            console.log('📡 Received game state:', data);
                            setGameState(data);
                        } catch (err) {
                            console.error('Failed to parse message:', err);
                        }
                    }
                };

                ws.onerror = (err) => {
                    console.error('❌ WebSocket error:', err);
                    if (mounted) {
                        setError('Connection error');
                    }
                };

                ws.onclose = () => {
                    console.log('🔌 WebSocket disconnected');
                    if (mounted) {
                        setConnected(false);
                        // Auto-reconnect after 3 seconds
                        reconnectTimeoutRef.current = setTimeout(() => {
                            if (mounted) {
                                console.log('🔄 Reconnecting...');
                                connect();
                            }
                        }, 3000);
                    }
                };

                wsRef.current = ws;

            } catch (err) {
                console.error('Failed to create WebSocket:', err);
                if (mounted) {
                    setError(err.message);
                }
            }
        }

        connect();

        // Cleanup
        return () => {
            mounted = false;
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [url]);

    return { gameState, connected, error };
}
