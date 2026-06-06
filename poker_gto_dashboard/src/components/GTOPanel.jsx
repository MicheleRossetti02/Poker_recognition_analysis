import { Zap, TrendingUp, TrendingDown, Minus } from 'lucide-react';

/**
 * GTOPanel - Large, prominent display of GTO recommendation
 * This is the MOST IMPORTANT component - shows clear action
 */
export default function GTOPanel({ suggestion = 'Waiting for hand...', color = 'gray' }) {
    // Color mapping
    const colors = {
        green: {
            bg: 'from-green-600 to-emerald-700',
            ring: 'ring-green-400',
            shadow: 'shadow-green-500/50',
            text: 'text-green-100',
            icon: TrendingUp
        },
        yellow: {
            bg: 'from-yellow-500 to-amber-600',
            ring: 'ring-yellow-400',
            shadow: 'shadow-yellow-500/50',
            text: 'text-yellow-900',
            icon: Minus
        },
        red: {
            bg: 'from-red-600 to-rose-700',
            ring: 'ring-red-400',
            shadow: 'shadow-red-500/50',
            text: 'text-red-100',
            icon: TrendingDown
        },
        gray: {
            bg: 'from-gray-700 to-gray-800',
            ring: 'ring-gray-600',
            shadow: 'shadow-gray-500/30',
            text: 'text-gray-400',
            icon: Zap
        }
    };

    const scheme = colors[color] || colors.gray;
    const Icon = scheme.icon;

    return (
        <div className={`
      bg-gradient-to-br ${scheme.bg}
      rounded-2xl p-8
      ring-4 ${scheme.ring}
      shadow-2xl ${scheme.shadow}
      transform transition-all duration-300
      hover:scale-105
      animate-pulse-subtle
    `}>
            {/* Header */}
            <div className="flex items-center justify-center gap-3 mb-4">
                <Zap className={`w-8 h-8 ${scheme.text}`} />
                <h2 className={`text-2xl font-bold ${scheme.text} tracking-wide`}>
                    GTO RECOMMENDATION
                </h2>
            </div>

            {/* Main Action Display */}
            <div className={`
        text-center py-6 px-4
        bg-black/20 rounded-xl
        border-2 border-white/10
      `}>
                <div className="flex items-center justify-center gap-4 mb-2">
                    <Icon className={`w-16 h-16 ${scheme.text}`} />
                    <p className={`
            text-6xl font-black ${scheme.text}
            tracking-tight leading-none
            drop-shadow-lg
          `}>
                        {suggestion}
                    </p>
                </div>
            </div>

            {/* Sub-info */}
            <div className="mt-4 text-center">
                <p className={`text-sm ${scheme.text} opacity-80`}>
                    Follow this recommendation for optimal GTO play
                </p>
            </div>
        </div>
    );
}
