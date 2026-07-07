# Main chat loop — orchestrates persona, session, message flow, and memory trimming
from app.memory import trim_memory
from app.config import textPrompt
from app.database import save_session, load_session, get_db
from app.cli import header, print_message, prompt_input, info
from app.response import get_response
from app.personalities import get_personalities, create_personality, pick_personality

def _cli_pick_personality():
    personalities = get_personalities()
    if not personalities:
        info("No personas found. Let's create one.")
        name = prompt_input("Name:").strip()
        description = prompt_input("Description (optional):").strip()
        system = prompt_input("System prompt:").strip()
        scenario = prompt_input("Scenario:").strip()
        first_msg = prompt_input("First Message:").strip()
        return create_personality(
            name=name,
            description=description,
            system=system,
            scenario=scenario,
            opening_prompt=first_msg,
        )

    header("Pick a personality")
    for key, val in personalities.items():
        print(f"  {key}. {val['name']}")
    print("  N. Create new persona")

    choice = prompt_input("Enter number or N:").strip().lower()
    result = pick_personality(choice)

    if result is None:
        name = prompt_input("Name:").strip()
        description = prompt_input("Description (optional):").strip()
        system = prompt_input("System prompt:").strip()
        scenario = prompt_input("Scenario:").strip()
        first_msg = prompt_input("First Message:").strip()
        return create_personality(
            name=name,
            description=description,
            system=system,
            scenario=scenario,
            opening_prompt=first_msg,
        )

    return result

def run():
    # Pick or create a persona, then greet the user
    persona = _cli_pick_personality()
    header(f"Now chatting with {persona['name']}")
    print("Type 'Exit' to quit.\n")

    # Build the system message from the persona's config + global style prompt
    template = f"{persona.get('system','')}\n\n{textPrompt}\n\nScenario: {persona.get('scenario','')}"  # FIXED: Changed 'Scenario' to 'scenario'
    system_message = {
        "role": "system",
        "content": template
    }

    # Load an existing session or start fresh (DB-backed)
    with get_db() as db:
        context, full_messages, existing_session = load_session(db, persona, system_message)
        messages = [
            {k: v for k, v in msg.items() if k != "id"}
            for msg in context
        ]

    # CLI-only: replay history to terminal
    if existing_session:
        print(f"Resuming session from {existing_session['created_at']}\n")
        for msg in full_messages:
            if msg["role"] == "system":
                continue
            print_message(msg["role"], persona["name"], msg["content"])
            if msg["role"] == "user":
                print()
    else:
        print_message("assistant", persona["name"], full_messages[-1]["content"])
        print()
    
    # Track how many user messages existed before this run (for save-on-exit logic)
    initial_user_count = sum(1 for m in messages if m.get("role") == "user")
    user_sent = False       # becomes True once the user sends their first message

    # full_messages is the complete untruncated history used for saving to DB
    message_id = max(
        (m.get("id", 0) for m in full_messages),
        default=0
    )

    while True:
        user_input = prompt_input("You:")
        print()
        if user_input == 'Exit':
            # Only save if the user actually sent something new this run
            if user_sent:  # FIXED: Simplified logic - only save if user sent something
                if existing_session:
                    save_session(db, persona["key"], full_messages, session_id=existing_session.get("id"))
                else:
                    save_session(db, persona["key"], full_messages)
            else:
                info("No new user messages — session not saved.")
            print("Exiting...")
            return

        messages.append({"role": "user", "content": user_input})
        
        user_sent = True
    
        # Call the LLM; on failure let the user retry rather than crashing
        assistant_msg = None
        try:
            assistant_msg = get_response(messages)
        except RuntimeError as e:
            print(f"[Error] Could not get a response: {e}")
            print("You can try again or type 'Exit' to quit.\n")
            continue

        print_message("assistant", persona["name"], assistant_msg)
        
        messages.append({"role": "assistant", "content": assistant_msg})
    
        # Summarize and compress history once the trim interval is reached
        message_id += 1
        full_messages.append({
            "id": message_id,
            "role": "user",
            "content": user_input
        })
        full_messages.append({
            "id": message_id + 1,
            "role": "assistant",
            "content": assistant_msg
        })
        message_id += 1  # Increment by 2 total (for user and assistant messages)
        
        messages = trim_memory(messages, system_message)

