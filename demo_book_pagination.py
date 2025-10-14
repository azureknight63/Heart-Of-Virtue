"""
Demonstration of the Book pagination system.
Run this script to see how the pagination works interactively.
"""
from src.objects import Book
from src.player import Player
from src.tiles import MapTile


class MockPlayer:
    """Minimal player for demo purposes."""
    name = "Jean"
    inventory = []


class MockTile:
    """Minimal tile for demo purposes."""
    pass


def demo_short_book():
    """Demonstrate a book with short text (no pagination)."""
    print("\n" + "=" * 80)
    print("DEMO 1: Short Book (No Pagination)")
    print("=" * 80 + "\n")
    
    player = MockPlayer()
    tile = MockTile()
    
    short_text = ("This is a brief note found in an old journal. "
                  "It speaks of courage and virtue in trying times.")
    
    book = Book(player, tile, text=short_text, description="A small, weathered journal.")
    book.read()


def demo_long_book():
    """Demonstrate a book with long text (with pagination)."""
    print("\n" + "=" * 80)
    print("DEMO 2: Long Book (With Pagination)")
    print("=" * 80 + "\n")
    
    player = MockPlayer()
    tile = MockTile()
    
    # Create a longer text that will be paginated
    long_text = """
The Chronicles of Virtue: An Ancient Text

In the beginning, there was only the void, a vast expanse of nothingness that stretched beyond comprehension. 
From this void emerged the first light, a spark of divine will that would shape the world to come. 
This light brought with it the seeds of creation, scattering them across the cosmos like stars in the night sky.

The first beings to walk this new world were the Ancients, creatures of immense power and wisdom. 
They looked upon the empty canvas of creation and saw infinite possibility. 
With care and deliberation, they began to shape the land, raising mountains from the plains and carving 
rivers through stone. They called forth forests from the barren earth and filled the seas with life.

But the Ancients knew that their work was not yet complete. The world they had created was beautiful, 
but it lacked something essential: it lacked virtue. And so they gathered together in council, 
debating long into the night about how to instill this most precious quality into their creation.

After much deliberation, they reached a decision. They would create beings in their own image, 
creatures capable of reason and choice, who could learn the nature of virtue through experience. 
These beings would be called humans, and they would be given the greatest gift of all: free will.

The first humans were like children, innocent and curious about the world around them. 
The Ancients taught them many things: how to build shelter, how to grow food, how to work together 
for the common good. But most importantly, they taught them about the Virtues—courage, compassion, 
wisdom, justice, temperance, and hope.

Yet the Ancients knew that merely teaching these virtues was not enough. True virtue could only be 
learned through struggle, through facing challenges and making difficult choices. And so they stepped 
back, allowing humanity to find its own path, to make its own mistakes, and to grow through adversity.

Centuries passed, and humanity spread across the land. Some embraced the teachings of virtue, 
building great civilizations founded on justice and compassion. Others turned away from these teachings, 
succumbing to greed, hatred, and fear. The world became a place of both great beauty and terrible darkness.

This is the world we inherit, a world shaped by the choices of those who came before us. 
And now, it falls to us to decide what kind of world we will leave for those who come after.
"""
    
    book = Book(player, tile, text=long_text.strip(), 
                description="An ancient tome bound in leather, its pages yellowed with age.",
                chars_per_page=500)
    
    print("TIP: Use 'n' for next page, 'p' for previous page, 'c' to close the book.")
    print()
    book.read()


def demo_custom_page_size():
    """Demonstrate a book with custom page size."""
    print("\n" + "=" * 80)
    print("DEMO 3: Custom Page Size (Very Small Pages)")
    print("=" * 80 + "\n")
    
    player = MockPlayer()
    tile = MockTile()
    
    text = ("A quick brown fox jumps over the lazy dog. "
            "The five boxing wizards jump quickly. "
            "How vexingly quick daft zebras jump! "
            "Pack my box with five dozen liquor jugs. "
            "The quick onyx goblin jumps over the lazy dwarf.")
    
    book = Book(player, tile, text=text, 
                description="A book of pangrams and tongue twisters.",
                chars_per_page=80)  # Very small pages for demo
    
    print("This book has very small pages to demonstrate the pagination system.")
    print()
    book.read()


if __name__ == "__main__":
    print("=" * 80)
    print("BOOK PAGINATION SYSTEM DEMO")
    print("=" * 80)
    
    import sys
    
    if len(sys.argv) > 1:
        demo_choice = sys.argv[1]
        if demo_choice == "1":
            demo_short_book()
        elif demo_choice == "2":
            demo_long_book()
        elif demo_choice == "3":
            demo_custom_page_size()
        else:
            print("Invalid demo choice. Use 1, 2, or 3.")
    else:
        print("\nThis demo shows three different book scenarios:")
        print("1. Short book (no pagination)")
        print("2. Long book (with pagination)")
        print("3. Custom page size (small pages)")
        print("\nRun this script with a number (1-3) to see a specific demo:")
        print("  python demo_book_pagination.py 1")
        print("  python demo_book_pagination.py 2")
        print("  python demo_book_pagination.py 3")
        print("\nOr run all demos:")
        
        input("\nPress Enter to see all demos...")
        
        demo_short_book()
        input("\nPress Enter for next demo...")
        
        demo_long_book()
        input("\nPress Enter for next demo...")
        
        demo_custom_page_size()
        
        print("\n" + "=" * 80)
        print("DEMO COMPLETE")
        print("=" * 80)
