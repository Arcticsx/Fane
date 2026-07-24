import sys
import types

from . import chat_router as _chat_router

app = _chat_router.app
get_personalities = _chat_router.get_personalities
create_personality = _chat_router.create_personality
update_personality = _chat_router.update_personality
delete_personality = _chat_router.delete_personality
pick_personality = _chat_router.pick_personality
save_session = _chat_router.save_session
load_session = _chat_router.load_session
get_session_by_index = _chat_router.get_session_by_index
get_recent_sessions = _chat_router.get_recent_sessions
get_sessions = _chat_router.get_sessions
delete_session = _chat_router.delete_session

# Re-export the module under the legacy name expected by tests.
sys.modules[__name__] = _chat_router
