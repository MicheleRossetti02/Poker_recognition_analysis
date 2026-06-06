import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react';

/**
 * Advisor Component
 * Displays GTO recommendation with action, frequency, and EV
 * 
 * @param {Object} props
 * @param {Object} props.result - API response from /api/analyze-spot
 * @param {boolean} props.loading - Loading state
 */
export default function Advisor({ result, loading }) {
    if (loading) {
        return (
            <div className="bg-gray-800/90 backdrop-blur-sm rounded-2xl p-6 shadow-2xl border border-gray-700 animate-pulse">
                <div className="h-6 bg-gray-700 rounded w-32 mb-4"></div>
                <div className="h-12 bg-gray-700 rounded w-24"></div>
            </div>
        );
    }

    if (!result) {
        return (
            <div className="bg-gray-800/80 backdrop-blur-sm rounded-2xl p-6 shadow-xl border border-gray-700">
                <div className="flex items-center gap-3 text-gray-400">
                    <AlertCircle className="w-5 h-5" />
                    <span>Select your cards and click "Analyze Hand"</span>
                </div>
            </div>
        );
    }

    // Determine colors based on action
    const actionColors = {
        raise: 'from-green-600 to-emerald-700 border-green-500',
        all_in: 'from-orange-600 to-amber-700 border-orange-500',
        call: 'from-blue-600 to-cyan-700 border-blue-500',
        fold: 'from-red-900 to-gray-800 border-red-700',
        check: 'from-gray-600 to-gray-700 border-gray-500'
    };

    const actionLabels = {
        raise: 'RAISE',
        all_in: 'ALL-IN',
        call: 'CALL',
        fold: 'FOLD',
        check: 'CHECK'
    };

    const action = result.action?.toLowerCase() || 'fold';
    const colorClass = actionColors[action] || actionColors.fold;
    const label = actionLabels[action] || result.action?.toUpperCase();

    const isPositiveEV = result.ev > 0;

    return (
        <div className={`bg-gradient-to-br ${colorClass} backdrop-blur-sm rounded-2xl p-6 shadow-2xl border-2`}>
            {/* Hand notation */}
            <div className="text-white/70 text-sm font-medium mb-2">
                {result.hand} • {result.scenario}
            </div>

            {/* Main action */}
            <div className="text-4xl font-black text-white tracking-wide mb-4">
                {label}
            </div>

            {/* Stats row */}
            <div className="flex items-center gap-6 text-white/90">
                {/* Frequency */}
                <div>
                    <div className="text-xs text-white/60 uppercase tracking-wide">Frequency</div>
                    <div className="text-lg font-bold">
                        {(result.frequency * 100).toFixed(0)}%
                    </div>
                </div>

                {/* EV */}
                <div>
                    <div className="text-xs text-white/60 uppercase tracking-wide">EV</div>
                    <div className={`text-lg font-bold flex items-center gap-1 ${isPositiveEV ? 'text-green-300' : 'text-red-300'}`}>
                        {isPositiveEV ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        {isPositiveEV ? '+' : ''}{result.ev?.toFixed(2)} BB
                    </div>
                </div>
            </div>

            {/* Alternative action */}
            {result.alternative_action && (
                <div className="mt-4 pt-4 border-t border-white/20 text-white/70 text-sm">
                    Alt: {result.alternative_action.toUpperCase()} ({(result.alternative_frequency * 100).toFixed(0)}%)
                </div>
            )}

            {/* Database indicator */}
            {result.found_in_database === false && (
                <div className="mt-4 text-yellow-300 text-xs flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    Default suggestion (hand not in database)
                </div>
            )}
        </div>
    );
}
