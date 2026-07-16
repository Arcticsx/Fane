# Handles conversation summarization and memory trimming
try:
    from .response import get_response
except ImportError:
    from response import get_response

def summarize(messages):
    # Sends the raw message list to the LLM and returns a plain-text summary
        
    summary_prompt = [
        {
            "role": "system",
            "content": """Act as a professional summarizer. Create a concise and comprehensive summary of the messages provided, while adhering to the guidelines enclosed in [ ] below. 

Guidelines:  

[ 

    Create a summary that is detailed, thorough, in-depth, and complex, while maintaining clarity and conciseness. 
    The summary must cover all the key points and main ideas presented in the original text, while also condensing the information into a concise and easy-to-understand format. 
    Ensure that the summary includes relevant details and examples that support the main ideas, while avoiding any unnecessary information or repetition. 
    Rely strictly on the provided text, without including external information. 
    The length of the summary must be appropriate for the length and complexity of the original text. The length must allow to capture the main points and key details, without being overly long.  
    Ensure that the summary is well-organized and easy to read, with clear headings and subheadings to guide the reader through each section. Format each section in paragraph form. 

]"""
        },
        {
            "role": "user",
            "content": f"Summarize this chat:\n\n{messages}"
        }
    ]
    return get_response(summary_prompt)


def trim_memory(messages, system_message):
    # Strip all system messages first so slicing only operates on user/assistant turns.
    # This prevents system message duplication across multiple trim cycles.
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) <= 10:
        return messages
    
    # Summarize everything except the 10 most recent exchanges
    old = non_system[:-10]
    new = non_system[-10:]
    summary = summarize(old)

    # Rebuild: fresh system message → summary → recent turns
    return [
        system_message,
        {"role": "system", "content": f"Conversation summary: {summary}"}
    ] + new
