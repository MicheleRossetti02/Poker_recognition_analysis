import { useState } from 'react';
import { X } from 'lucide-react';
import Card, { ALL_CARDS } from './Card';

/**
 * CardSelectorModal
 * Modal popup to select hole cards from a grid of 52 cards
 * 
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether modal is open
 * @param {function} props.onClose - Close handler
 * @param {function} props.onSelect - Callback with selected cards array
 * @param {string[]} props.selectedCards - Currently selected cards
 * @param {string[]} props.disabledCards - Cards that cannot be selected
 * @param {number} props.maxCards - Maximum cards to select (default 2)
 */
export default function CardSelectorModal({
    isOpen,
    onClose,
    onSelect,
    selectedCards = [],
    disabledCards = [],
    maxCards = 2
}) {
    const [tempSelection, setTempSelection] = useState(selectedCards);

    if (!isOpen) return null;

    const handleCardClick = (card) => {
        if (disabledCards.includes(card)) return;

        if (tempSelection.includes(card)) {
            // Deselect
            setTempSelection(tempSelection.filter(c => c !== card));
        } else if (tempSelection.length < maxCards) {
            // Select
            setTempSelection([...tempSelection, card]);
        }
    };

    const handleConfirm = () => {
        onSelect(tempSelection);
        onClose();
    };

    const handleClear = () => {
        setTempSelection([]);
    };

    // Group cards by suit
    const suits = ['s', 'h', 'd', 'c'];
    const suitNames = { s: 'Spades ♠', h: 'Hearts ♥', d: 'Diamonds ♦', c: 'Clubs ♣' };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
            <div className="bg-gray-900 rounded-2xl p-6 max-w-2xl w-full mx-4 shadow-2xl border border-gray-700">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold text-white">Select Your Cards</h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
                    >
                        <X className="w-6 h-6 text-gray-400" />
                    </button>
                </div>

                {/* Selected cards preview */}
                <div className="flex items-center gap-4 mb-6 p-4 bg-gray-800 rounded-xl">
                    <span className="text-gray-400">Selected:</span>
                    <div className="flex gap-2">
                        {tempSelection.length > 0 ? (
                            tempSelection.map(card => (
                                <Card key={card} card={card} small />
                            ))
                        ) : (
                            <span className="text-gray-500">No cards selected</span>
                        )}
                    </div>
                    {tempSelection.length > 0 && (
                        <button
                            onClick={handleClear}
                            className="ml-auto text-red-400 hover:text-red-300 text-sm"
                        >
                            Clear
                        </button>
                    )}
                </div>

                {/* Card grid by suit */}
                <div className="space-y-4 max-h-96 overflow-y-auto">
                    {suits.map(suit => (
                        <div key={suit}>
                            <h3 className={`text-sm font-medium mb-2 ${suit === 'h' || suit === 'd' ? 'text-red-400' : 'text-gray-400'}`}>
                                {suitNames[suit]}
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {ALL_CARDS.filter(c => c[1] === suit).map(card => (
                                    <Card
                                        key={card}
                                        card={card}
                                        small
                                        selected={tempSelection.includes(card)}
                                        disabled={disabledCards.includes(card)}
                                        onClick={() => handleCardClick(card)}
                                    />
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Actions */}
                <div className="flex gap-4 mt-6">
                    <button
                        onClick={onClose}
                        className="flex-1 py-3 px-6 rounded-xl bg-gray-700 text-white font-medium hover:bg-gray-600 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleConfirm}
                        disabled={tempSelection.length !== maxCards}
                        className={`
              flex-1 py-3 px-6 rounded-xl font-medium transition-colors
              ${tempSelection.length === maxCards
                                ? 'bg-yellow-500 text-gray-900 hover:bg-yellow-400'
                                : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                            }
            `}
                    >
                        Confirm ({tempSelection.length}/{maxCards})
                    </button>
                </div>
            </div>
        </div>
    );
}
