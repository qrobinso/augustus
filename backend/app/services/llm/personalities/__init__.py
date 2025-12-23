"""Personality definitions for cast members.

Each personality defines how a cast member behaves, speaks, and contributes to briefings.
"""

from app.services.llm.personalities.base import Personality
from app.services.llm.personalities.casual import Casual
from app.services.llm.personalities.professional import Professional
from app.services.llm.personalities.analytical import Analytical
from app.services.llm.personalities.friendly import Friendly
from app.services.llm.personalities.informative import Informative
from app.services.llm.personalities.upbeat import Upbeat
from app.services.llm.personalities.provocateur import Provocateur
from app.services.llm.personalities.businessman import Businessman
from app.services.llm.personalities.scholar import Scholar
from app.services.llm.personalities.storyteller import Storyteller
from app.services.llm.personalities.skeptic import Skeptic
from app.services.llm.personalities.optimist import Optimist
from app.services.llm.personalities.realist import Realist

# Registry of all available personalities
PERSONALITY_REGISTRY = {
    "Casual": Casual,
    "Professional": Professional,
    "Analytical": Analytical,
    "Friendly": Friendly,
    "Informative": Informative,
    "Upbeat": Upbeat,
    "The Provocateur/Truth-Teller": Provocateur,
    "The Businessman/Everyman": Businessman,
    "The Scholar/Researcher": Scholar,
    "The Storyteller": Storyteller,
    "The Skeptic": Skeptic,
    "The Optimist": Optimist,
    "The Realist": Realist,
}


def get_personality(name: str) -> Personality:
    """Get a personality instance by name.
    
    This function first checks the registry, then dynamically discovers
    personalities from files if not found in the registry.
    
    Args:
        name: The personality name
        
    Returns:
        Personality instance
        
    Raises:
        ValueError: If personality name is not found
    """
    # First, try the registry
    personality_class = PERSONALITY_REGISTRY.get(name)
    if personality_class is not None:
        return personality_class()
    
    # If not in registry, try to discover dynamically
    try:
        from pathlib import Path
        import importlib
        import inspect
        import sys
        
        # Get the personalities directory path (this file is in the personalities directory)
        personalities_dir = Path(__file__).parent
        
        # Search through all Python files
        for file_path in personalities_dir.glob("*.py"):
            if file_path.name in ("__init__.py", "base.py"):
                continue
            
            try:
                module_name = file_path.stem
                module_path = f"app.services.llm.personalities.{module_name}"
                # Reload if already imported to pick up changes
                if module_path in sys.modules:
                    module = importlib.reload(sys.modules[module_path])
                else:
                    module = importlib.import_module(module_path)
                
                # Find Personality subclasses
                for obj_name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, Personality) and 
                        obj is not Personality and 
                        obj.__module__ == module_path):
                        instance = obj()
                        if instance.name == name:
                            return instance
            except Exception:
                continue
        
        # If still not found, fallback to Casual
        return Casual()
    except Exception:
        # If dynamic discovery fails, fallback to Casual
        return Casual()


def get_all_personalities() -> dict[str, Personality]:
    """Get all available personalities.
    
    Returns:
        Dictionary mapping personality names to instances
    """
    return {name: cls() for name, cls in PERSONALITY_REGISTRY.items()}

