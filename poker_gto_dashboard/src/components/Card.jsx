import { Heart, Diamond, Club, Spade } from 'lucide-react';

/**
 * Card Component
 * Displays a playing card with rank and suit
 * 
 * @param {Object} props
 * @param {string} props.card - Card notation (e.g., "Ah", "Ks", "Td")
 * @param {boolean} props.selected - Whether the card is selected
 * @param {boolean} props.small - Render smaller version
 * @param {function} props.onClick - Click handler
 */
export default function Card({ card, selected = false, small = false, onClick, disabled = false }) {
    if (!card) {
        // Empty card slot
        return (
            <div
                className={`
          ${small ? 'w-10 h-14' : 'w-16 h-24'} 
          rounded-lg border-2 border-dashed border-gray-500 
          bg-gray-800/50 flex items-center justify-center
          ${onClick && !disabled ? 'cursor-pointer hover:border-yellow-400 hover:bg-gray-700/50' : ''}
        `}
                onClick={!disabled ? onClick : undefined}
            >
                <span className="text-gray-500 text-xl">?</span>
            </div>
        );
    }

    const rank = card[0];
    const suit = card[1];

    // Determine if red suit (hearts or diamonds)
    const isRed = suit === 'h' || suit === 'd';

    // Get suit icon
    const SuitIcon = {
        'h': Heart,
        'd': Diamond,
        'c': Club,
        's': Spade,
    }[suit] || Spade;

    // Display rank (T = 10)
    const displayRank = rank === 'T' ? '10' : rank;

    return (
        <div
            className={`
        ${small ? 'w-10 h-14' : 'w-16 h-24'} 
        rounded-lg shadow-lg 
        flex flex-col items-center justify-center gap-1
        transition-all duration-200
        ${selected
                    ? 'ring-4 ring-yellow-400 scale-105 bg-white'
                    : 'bg-white hover:scale-105'
                }
        ${onClick && !disabled ? 'cursor-pointer' : ''}
        ${disabled ? 'opacity-50' : ''}
      `}
            onClick={!disabled ? onClick : undefined}
        >
            <span
                className={`
          ${small ? 'text-lg' : 'text-2xl'} 
          font-bold 
          ${isRed ? 'text-red-600' : 'text-gray-900'}
        `}
            >
                {displayRank}
            </span>
            <SuitIcon
                className={`
          ${small ? 'w-4 h-4' : 'w-6 h-6'} 
          ${isRed ? 'text-red-600 fill-red-600' : 'text-gray-900 fill-gray-900'}
        `}
            />
        </div>
    );
}


/**
 * Generate all 52 cards in a standard deck
 */
export const ALL_CARDS = (() => {
    const ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
    const suits = ['s', 'h', 'd', 'c'];
    const cards = [];

    for (const suit of suits) {
        for (const rank of ranks) {
            cards.push(`${rank}${suit}`);
        }
    }

    return cards;
})();
