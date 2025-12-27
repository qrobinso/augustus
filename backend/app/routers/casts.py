"""Casts API router."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.cast import (
    CastCreate,
    CastUpdate,
    CastResponse,
    CastListResponse,
    CastMemberBase,
)
from app.services.cast import CastService
from app.services.llm.openrouter import get_llm_provider

# Import personalities registry with error handling
try:
    from app.services.llm.personalities import PERSONALITY_REGISTRY
except ImportError as e:
    print(f"[Casts] Warning: Failed to import PERSONALITY_REGISTRY: {e}")
    # Fallback to empty registry if import fails
    PERSONALITY_REGISTRY = {}

router = APIRouter()


@router.post("", response_model=CastResponse, status_code=status.HTTP_201_CREATED)
async def create_cast(
    cast_data: CastCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new cast."""
    service = CastService(db)
    try:
        cast = await service.create_cast(user.id, cast_data)
        return CastResponse.model_validate(cast)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=CastListResponse)
async def list_casts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all casts for the current user."""
    service = CastService(db)
    casts = await service.get_user_casts(user.id)
    return CastListResponse(casts=[CastResponse.model_validate(c) for c in casts])


@router.get("/personalities", response_model=list[str])
async def list_personalities(
    user: User = Depends(get_current_user),
):
    """List all available personalities.
    
    Returns a list of personality names that can be used when creating cast members.
    This endpoint dynamically discovers personalities from the personalities directory,
    so new personalities will automatically appear in the list.
    """
    try:
        from pathlib import Path
        import importlib
        import inspect
        import sys
        from app.services.llm.personalities.base import Personality
        
        # Get the personalities directory path (more robust)
        # __file__ is in app/routers/casts.py, so we need to go up to app, then to services/llm/personalities
        current_file = Path(__file__)
        # Go from app/routers/casts.py -> app/routers -> app -> app/services/llm/personalities
        personalities_dir = current_file.parent.parent / "services" / "llm" / "personalities"
        
        # Alternative: use importlib to find the module path
        try:
            import app.services.llm.personalities as personalities_module
            personalities_dir = Path(personalities_module.__file__).parent
        except Exception:
            pass  # Fall back to calculated path
        
        # Discover all Python files in the personalities directory
        personality_names = set()
        
        # First, add names from the registry (for backward compatibility)
        if PERSONALITY_REGISTRY:
            personality_names.update(PERSONALITY_REGISTRY.keys())
        
        # Then, dynamically discover from files
        for file_path in personalities_dir.glob("*.py"):
            # Skip __init__.py and base.py
            if file_path.name in ("__init__.py", "base.py", "__pycache__"):
                continue
            
            try:
                # Get module name (e.g., "casual" from "casual.py")
                module_name = file_path.stem
                
                # Import the module dynamically
                module_path = f"app.services.llm.personalities.{module_name}"
                
                # Try to import, skip if it fails
                # Use importlib.reload if module already imported to pick up changes
                try:
                    if module_path in sys.modules:
                        module = importlib.reload(sys.modules[module_path])
                    else:
                        module = importlib.import_module(module_path)
                except Exception as e:
                    print(f"[Casts] Warning: Could not import {module_path}: {e}")
                    continue
                
                # Find all classes in the module that inherit from Personality
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a Personality subclass and not the base class itself
                    if (issubclass(obj, Personality) and 
                        obj is not Personality and 
                        obj.__module__ == module_path):
                        # Get the personality name from the instance
                        try:
                            instance = obj()
                            personality_name = instance.name
                            personality_names.add(personality_name)
                        except Exception as e:
                            print(f"[Casts] Warning: Could not instantiate {name} from {module_path}: {e}")
                            continue
            except Exception as e:
                print(f"[Casts] Warning: Error processing {file_path.name}: {e}")
                continue
        
        # Return sorted list
        return sorted(personality_names)
    except Exception as e:
        # Log error and return registry keys as fallback
        print(f"[Casts] Error discovering personalities: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to registry if dynamic discovery fails
        try:
            return sorted(PERSONALITY_REGISTRY.keys()) if PERSONALITY_REGISTRY else []
        except:
            return []


@router.get("/{cast_id}", response_model=CastResponse)
async def get_cast(
    cast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a cast by ID."""
    service = CastService(db)
    cast = await service.get_cast(cast_id, user.id)
    if not cast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
    return CastResponse.model_validate(cast)


@router.put("/{cast_id}", response_model=CastResponse)
async def update_cast(
    cast_id: str,
    cast_data: CastUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a cast."""
    service = CastService(db)
    try:
        cast = await service.update_cast(cast_id, user.id, cast_data)
        if not cast:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
        return CastResponse.model_validate(cast)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{cast_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cast(
    cast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cast."""
    service = CastService(db)
    try:
        deleted = await service.delete_cast(cast_id, user.id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{cast_id}/set-default", response_model=CastResponse)
async def set_default_cast(
    cast_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a cast as the default for the user."""
    service = CastService(db)
    cast = await service.set_default_cast(cast_id, user.id)
    if not cast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cast not found")
    return CastResponse.model_validate(cast)


@router.post("/default/restore", response_model=CastResponse)
async def restore_default_cast(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore the default cast to its original values (Alex and Sam with Kore/Puck voices)."""
    service = CastService(db)
    cast = await service.restore_default_cast(user.id)
    return CastResponse.model_validate(cast)


# Personality file management endpoints
@router.get("/personalities/files", response_model=list[dict])
async def list_personality_files(
    user: User = Depends(get_current_user),
):
    """List all personality files.
    
    Returns a list of personality file metadata (name, filename, etc.)
    """
    try:
        from pathlib import Path
        import app.services.llm.personalities as personalities_module
        
        personalities_dir = Path(personalities_module.__file__).parent
        
        files = []
        for file_path in sorted(personalities_dir.glob("*.py")):
            # Skip __init__.py and base.py
            if file_path.name in ("__init__.py", "base.py"):
                continue
            
            files.append({
                "filename": file_path.name,
                "name": file_path.stem,
                "path": str(file_path.relative_to(personalities_dir.parent.parent.parent)),
            })
        
        return files
    except Exception as e:
        print(f"[Casts] Error listing personality files: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list personality files: {str(e)}"
        )


@router.get("/personalities/files/{filename:path}")
async def get_personality_file(
    filename: str,
    user: User = Depends(get_current_user),
):
    """Get the content of a personality file."""
    try:
        from pathlib import Path
        import app.services.llm.personalities as personalities_module
        
        personalities_dir = Path(personalities_module.__file__).parent
        file_path = personalities_dir / filename
        
        # Security: ensure the file is within the personalities directory
        if not file_path.resolve().is_relative_to(personalities_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Don't allow reading __init__.py or base.py
        if filename in ("__init__.py", "base.py"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot read this file"
            )
        
        content = file_path.read_text(encoding='utf-8')
        
        return {
            "filename": filename,
            "name": file_path.stem,
            "content": content,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Casts] Error reading personality file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )


@router.put("/personalities/files/{filename:path}")
async def save_personality_file(
    filename: str,
    request: dict,
    user: User = Depends(get_current_user),
):
    """Save/update a personality file."""
    try:
        from pathlib import Path
        
        file_content = request.get("content", "")
        
        import app.services.llm.personalities as personalities_module
        
        personalities_dir = Path(personalities_module.__file__).parent
        file_path = personalities_dir / filename
        
        # Security: ensure the file is within the personalities directory
        if not file_path.resolve().is_relative_to(personalities_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Don't allow editing __init__.py or base.py
        if filename in ("__init__.py", "base.py"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot edit this file"
            )
        
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content is required"
            )
        
        # Write the file
        file_path.write_text(file_content, encoding='utf-8')
        
        return {
            "filename": filename,
            "name": file_path.stem,
            "message": "File saved successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Casts] Error saving personality file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )


@router.post("/personalities/files")
async def create_personality_file(
    request: dict,
    user: User = Depends(get_current_user),
):
    """Create a new personality file."""
    try:
        from pathlib import Path
        
        import app.services.llm.personalities as personalities_module
        
        personalities_dir = Path(personalities_module.__file__).parent
        
        filename = request.get("filename", "").strip()
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        # Ensure .py extension
        if not filename.endswith(".py"):
            filename += ".py"
        
        # Validate filename (no path traversal, no special files)
        if "/" in filename or "\\" in filename or filename in ("__init__.py", "base.py"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )
        
        file_path = personalities_dir / filename
        
        # Check if file already exists
        if file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="File already exists"
            )
        
        # Get content or use template
        content = request.get("content", "")
        if not content:
            # Use template
            personality_name = file_path.stem.capitalize()
            content = f'''"""{personality_name} personality - description here."""

from app.services.llm.personalities.base import Personality


class {personality_name}(Personality):
    """Description here."""
    
    @property
    def name(self) -> str:
        return "{personality_name}"
    
    @property
    def core_trait(self) -> str:
        return "Core trait description"
    
    @property
    def voice(self) -> str:
        return "Voice description"
    
    @property
    def role(self) -> str:
        return "Role description"
    
    @property
    def personality_params(self) -> str:
        return "Personality parameters"
    
    def get_behavioral_guidelines(self) -> list[str]:
        return [
            "Guideline 1",
            "Guideline 2",
            "Guideline 3",
        ]

'''
        
        # Write the file
        file_path.write_text(content, encoding='utf-8')
        
        return {
            "filename": filename,
            "name": file_path.stem,
            "message": "File created successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Casts] Error creating personality file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create file: {str(e)}"
        )


@router.delete("/personalities/files/{filename:path}")
async def delete_personality_file(
    filename: str,
    user: User = Depends(get_current_user),
):
    """Delete a personality file."""
    try:
        from pathlib import Path
        
        import app.services.llm.personalities as personalities_module
        
        personalities_dir = Path(personalities_module.__file__).parent
        file_path = personalities_dir / filename
        
        # Security: ensure the file is within the personalities directory
        if not file_path.resolve().is_relative_to(personalities_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Don't allow deleting __init__.py or base.py
        if filename in ("__init__.py", "base.py"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete this file"
            )
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Delete the file
        file_path.unlink()
        
        return {
            "filename": filename,
            "message": "File deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Casts] Error deleting personality file: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


class GenerateDescriptionRequest(BaseModel):
    """Request schema for generating cast description."""
    name: str
    members: list[CastMemberBase]


class GenerateDescriptionResponse(BaseModel):
    """Response schema for generated description."""
    description: str


@router.post("/generate-description", response_model=GenerateDescriptionResponse)
async def generate_cast_description(
    request: GenerateDescriptionRequest,
    user: User = Depends(get_current_user),
):
    """Generate a cast description using the LLM.
    
    This endpoint uses the general LLM (from settings) to generate a description
    of how the cast works based on the cast name and members.
    """
    try:
        # Get LLM provider (uses general model from settings)
        llm = get_llm_provider()
        
        # Build prompt with cast information
        members_info = []
        for i, member in enumerate(request.members, 1):
            members_info.append(
                f"- {member.name}: {member.personality} personality"
            )
        
        members_text = "\n".join(members_info)
        
        system_prompt = """You are a helpful assistant that creates descriptions for podcast casts. 
Your descriptions should explain how the cast works, their dynamic, and any special characteristics 
that would help guide the briefing writer in creating content for this cast. Keep descriptions 
concise and focused on the cast's style and approach. Maximum 500 characters."""
        
        user_prompt = f"""Create a description for a podcast cast called "{request.name}".

Cast members:
{members_text}

Write a brief, concise description (maximum 500 characters) explaining how this cast works, their dynamic, 
and what makes them unique. This description will be used to guide the briefing writer 
in creating podcast scripts for this cast. Focus on the overall style, tone, and approach 
of the cast based on the personalities of the members. Be concise and direct."""
        
        # Generate description
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=200,  # Reduced tokens to encourage shorter output
            temperature=0.7,
        )
        
        description = response.content.strip()
        
        # Clean up the description (remove quotes if wrapped)
        if description.startswith('"') and description.endswith('"'):
            description = description[1:-1]
        if description.startswith("'") and description.endswith("'"):
            description = description[1:-1]
        
        # Enforce 500 character limit
        if len(description) > 500:
            description = description[:497] + "..."
        
        return GenerateDescriptionResponse(description=description)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM configuration error: {str(e)}"
        )
    except Exception as e:
        print(f"[Casts] Error generating description: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate description: {str(e)}"
        )






