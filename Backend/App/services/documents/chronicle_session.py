from ..utility.getdb import get_db
from ...models.rpg_sessions import RpgSession

def create_session(title, synopsis, genre, magic_rules_md = "", context_token_limit = ""):
    
    with get_db() as db:

        session = RpgSession(
            title=title,
            synopsis=synopsis,
            genre=genre,
            magic_rules_md=magic_rules_md,
            context_token_limit=context_token_limit,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    return session
