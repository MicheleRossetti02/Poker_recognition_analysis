import { useState, useMemo } from 'react';
import { User, Crown, Zap, Users, Target } from 'lucide-react';
import Card from './Card';
import CardSelectorModal from './CardSelectorModal';
import Advisor from './Advisor';
import { analyzeSpot } from '../services/api';

/**
 * Position configurations for different table sizes
 */
const TABLE_CONFIGS = {
    '6-max': {
        positions: [
            { id: 'BTN', label: 'BTN', angle: 270 },
            { id: 'SB', label: 'SB', angle: 210 },
            { id: 'BB', label: 'BB', angle: 150 },
            { id: 'UTG', label: 'UTG', angle: 90 },
            { id: 'MP', label: 'MP', angle: 30 },
            { id: 'CO', label: 'CO', angle: 330 },
        ]
    },
    '9-max': {
        positions: [
            { id: 'BTN', label: 'BTN', angle: 270 },
            { id: 'SB', label: 'SB', angle: 230 },
            { id: 'BB', label: 'BB', angle: 190 },
            { id: 'UTG', label: 'UTG', angle: 150 },
            { id: 'UTG1', label: 'UTG+1', angle: 110 },
            { id: 'MP', label: 'MP', angle: 70 },
            { id: 'MP1', label: 'MP+1', angle: 30 },
            { id: 'CO', label: 'CO', angle: 350 },
            { id: 'HJ', label: 'HJ', angle: 310 },
        ]
    },
    'heads-up': {
        positions: [
            { id: 'BTN', label: 'BTN/SB', angle: 270 },
            { id: 'BB', label: 'BB', angle: 90 },
        ]
    }
};

/**
 * Scenario modes for analysis
 */
const SCENARIO_MODES = [
    { id: 'rfi', label: 'Open Raise (RFI)', description: 'First to act - no villain yet' },
    { id: 'vs', label: 'Facing Opponent', description: 'Responding to villain action' },
];

/**
 * PokerTable Component
 * Main poker table visualization with seat positions
 */
export default function PokerTable() {
    // Table configuration
    const [tableSize, setTableSize] = useState('6-max');

    // Game state
    const [heroCards, setHeroCards] = useState([]);
    const [heroPosition, setHeroPosition] = useState('BTN');
    const [villainPosition, setVillainPosition] = useState('BB');
    const [stackSize, setStackSize] = useState(100);
    const [scenarioMode, setScenarioMode] = useState('rfi');

    // UI state
    const [showCardSelector, setShowCardSelector] = useState(false);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Get current positions based on table size
    const positions = useMemo(() => {
        return TABLE_CONFIGS[tableSize]?.positions || TABLE_CONFIGS['6-max'].positions;
    }, [tableSize]);

    // When table size changes, reset positions if needed
    const handleTableSizeChange = (newSize) => {
        setTableSize(newSize);
        const newPositions = TABLE_CONFIGS[newSize].positions;
        // Reset hero position if current one doesn't exist in new table
        if (!newPositions.find(p => p.id === heroPosition)) {
            setHeroPosition(newPositions[0].id);
        }
        if (!newPositions.find(p => p.id === villainPosition)) {
            setVillainPosition(newPositions[1]?.id || newPositions[0].id);
        }
    };

    const handleAnalyze = async () => {
        if (heroCards.length !== 2) {
            setError('Please select 2 cards');
            return;
        }

        if (stackSize < 1 || stackSize > 500) {
            setError('Stack must be between 1 and 500 BB');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            // For RFI scenarios, use "open" suffix; for vs scenarios, use villain position
            const scenarioSuffix = scenarioMode === 'rfi' ? 'open' : villainPosition;

            const response = await analyzeSpot({
                hero_position: heroPosition,
                villain_position: scenarioMode === 'rfi' ? 'BB' : villainPosition, // Default to BB for RFI
                stack: parseInt(stackSize, 10),
                hand: heroCards,
            });
            setResult(response);
        } catch (err) {
            setError(err.response?.data?.detail || 'Analysis failed');
            console.error('API Error:', err);
        } finally {
            setLoading(false);
        }
    };

    // Calculate seat position on the oval
    const getSeatPosition = (angle) => {
        const radiusX = 42;
        const radiusY = 38;
        const rad = (angle * Math.PI) / 180;
        return {
            left: `${50 + radiusX * Math.cos(rad)}%`,
            top: `${50 + radiusY * Math.sin(rad)}%`,
        };
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-4">
            {/* Header */}
            <header className="text-center mb-6">
                <h1 className="text-4xl font-bold text-white mb-2 flex items-center justify-center gap-3">
                    <Crown className="w-10 h-10 text-yellow-400" />
                    Poker Advisor
                </h1>
                <p className="text-gray-400">Select your cards and get GTO recommendations</p>
            </header>

            {/* Controls Bar */}
            <div className="flex flex-wrap items-center justify-center gap-4 mb-6 p-4 bg-gray-800/50 rounded-xl backdrop-blur-sm">

                {/* Table Size Selector */}
                <div>
                    <label className="block text-xs text-gray-400 mb-1">
                        <Users className="w-3 h-3 inline mr-1" />
                        Table
                    </label>
                    <div className="flex gap-1">
                        {Object.keys(TABLE_CONFIGS).map(size => (
                            <button
                                key={size}
                                onClick={() => handleTableSizeChange(size)}
                                className={`px-3 py-2 rounded-lg font-medium text-sm transition-colors ${tableSize === size
                                        ? 'bg-purple-600 text-white'
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                    }`}
                            >
                                {size}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Scenario Mode Toggle */}
                <div>
                    <label className="block text-xs text-gray-400 mb-1">
                        <Target className="w-3 h-3 inline mr-1" />
                        Scenario
                    </label>
                    <div className="flex gap-1">
                        {SCENARIO_MODES.map(mode => (
                            <button
                                key={mode.id}
                                onClick={() => setScenarioMode(mode.id)}
                                title={mode.description}
                                className={`px-3 py-2 rounded-lg font-medium text-sm transition-colors ${scenarioMode === mode.id
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                    }`}
                            >
                                {mode.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Hero Position */}
                <div>
                    <label className="block text-xs text-gray-400 mb-1">Hero Position</label>
                    <select
                        value={heroPosition}
                        onChange={(e) => setHeroPosition(e.target.value)}
                        className="bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600 focus:border-yellow-400 focus:outline-none"
                    >
                        {positions.map(p => (
                            <option key={p.id} value={p.id}>{p.label}</option>
                        ))}
                    </select>
                </div>

                {/* Villain Position - Only shown in 'vs' mode */}
                {scenarioMode === 'vs' && (
                    <div>
                        <label className="block text-xs text-gray-400 mb-1">Villain Position</label>
                        <select
                            value={villainPosition}
                            onChange={(e) => setVillainPosition(e.target.value)}
                            className="bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600 focus:border-yellow-400 focus:outline-none"
                        >
                            {positions.filter(p => p.id !== heroPosition).map(p => (
                                <option key={p.id} value={p.id}>{p.label}</option>
                            ))}
                        </select>
                    </div>
                )}

                {/* Stack Size - Manual Input */}
                <div>
                    <label className="block text-xs text-gray-400 mb-1">Stack (BB)</label>
                    <div className="flex items-center gap-2">
                        <input
                            type="number"
                            min="1"
                            max="500"
                            value={stackSize}
                            onChange={(e) => setStackSize(e.target.value)}
                            className="w-20 bg-gray-700 text-white px-3 py-2 rounded-lg border border-gray-600 focus:border-yellow-400 focus:outline-none text-center"
                        />
                        {/* Quick preset buttons */}
                        <div className="flex gap-1">
                            {[20, 50, 100].map(size => (
                                <button
                                    key={size}
                                    onClick={() => setStackSize(size)}
                                    className={`px-2 py-1 rounded text-xs transition-colors ${parseInt(stackSize) === size
                                            ? 'bg-yellow-500 text-gray-900'
                                            : 'bg-gray-600 text-gray-400 hover:bg-gray-500'
                                        }`}
                                >
                                    {size}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Table Area */}
            <div className="relative w-full max-w-4xl aspect-[16/10]">
                {/* Poker Table (Green Oval) */}
                <div className="absolute inset-8 rounded-[50%] bg-gradient-to-br from-emerald-800 to-green-900 shadow-2xl border-8 border-amber-900">
                    {/* Table felt texture overlay */}
                    <div className="absolute inset-0 rounded-[50%] bg-[radial-gradient(ellipse_at_center,_transparent_0%,_rgba(0,0,0,0.3)_100%)]"></div>

                    {/* Table rail */}
                    <div className="absolute -inset-2 rounded-[50%] border-4 border-amber-800 pointer-events-none"></div>

                    {/* Center content - Analyze button & Advisor */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 p-8">
                        {/* Scenario indicator */}
                        <div className="text-gray-300 text-sm bg-gray-800/60 px-3 py-1 rounded-full">
                            {scenarioMode === 'rfi'
                                ? `${heroPosition} Open Raise • ${stackSize}bb`
                                : `${heroPosition} vs ${villainPosition} • ${stackSize}bb`
                            }
                        </div>

                        {/* Advisor Result */}
                        <div className="w-full max-w-xs">
                            <Advisor result={result} loading={loading} />
                        </div>

                        {/* Error display */}
                        {error && (
                            <div className="bg-red-900/80 text-red-200 px-4 py-2 rounded-lg text-sm">
                                {error}
                            </div>
                        )}

                        {/* Analyze Button */}
                        <button
                            onClick={handleAnalyze}
                            disabled={heroCards.length !== 2 || loading}
                            className={`
                px-8 py-4 rounded-xl font-bold text-lg shadow-lg
                transition-all duration-300 transform
                flex items-center gap-2
                ${heroCards.length === 2 && !loading
                                    ? 'bg-gradient-to-r from-yellow-500 to-amber-500 text-gray-900 hover:scale-105 hover:shadow-yellow-500/30'
                                    : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                }
              `}
                        >
                            <Zap className="w-5 h-5" />
                            {loading ? 'Analyzing...' : 'ANALYZE HAND'}
                        </button>
                    </div>
                </div>

                {/* Seat Positions */}
                {positions.map(pos => {
                    const position = getSeatPosition(pos.angle);
                    const isHeroSeat = pos.id === heroPosition;
                    const isVillainSeat = scenarioMode === 'vs' && pos.id === villainPosition;

                    return (
                        <div
                            key={pos.id}
                            className="absolute transform -translate-x-1/2 -translate-y-1/2"
                            style={position}
                        >
                            {/* Seat circle */}
                            <div
                                className={`
                  w-16 h-16 md:w-20 md:h-20 rounded-full flex flex-col items-center justify-center
                  transition-all duration-300 cursor-pointer
                  ${isHeroSeat
                                        ? 'bg-gradient-to-br from-yellow-600 to-amber-700 ring-4 ring-yellow-400 shadow-lg shadow-yellow-500/30'
                                        : isVillainSeat
                                            ? 'bg-gradient-to-br from-red-700 to-red-900 ring-2 ring-red-500'
                                            : 'bg-gray-800 hover:bg-gray-700 border-2 border-gray-600'
                                    }
                `}
                                onClick={isHeroSeat ? () => setShowCardSelector(true) : undefined}
                            >
                                {/* Position label */}
                                <span className={`text-xs font-bold ${isHeroSeat ? 'text-yellow-100' :
                                        isVillainSeat ? 'text-red-200' :
                                            'text-gray-400'
                                    }`}>
                                    {pos.label}
                                </span>

                                {/* Cards or User icon */}
                                {isHeroSeat && heroCards.length > 0 ? (
                                    <div className="flex -space-x-2 mt-1">
                                        {heroCards.map(card => (
                                            <Card key={card} card={card} small />
                                        ))}
                                    </div>
                                ) : (
                                    <User className={`w-5 h-5 ${isHeroSeat ? 'text-yellow-200' :
                                            isVillainSeat ? 'text-red-300' :
                                                'text-gray-500'
                                        }`} />
                                )}
                            </div>

                            {/* Seat label */}
                            {(isHeroSeat || isVillainSeat) && (
                                <div className={`absolute -bottom-5 left-1/2 transform -translate-x-1/2 font-bold text-xs ${isHeroSeat ? 'text-yellow-400' : 'text-red-400'
                                    }`}>
                                    {isHeroSeat ? 'HERO' : 'VILLAIN'}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Card Selector Modal */}
            <CardSelectorModal
                isOpen={showCardSelector}
                onClose={() => setShowCardSelector(false)}
                onSelect={setHeroCards}
                selectedCards={heroCards}
                maxCards={2}
            />

            {/* Footer hint */}
            <p className="text-gray-500 text-sm mt-8">
                Click on HERO seat to select hole cards
            </p>
        </div>
    );
}
