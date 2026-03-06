"""Tool declarations and system prompt for Live API CUA mode."""

SYSTEM_PROMPT = """\
You are a helpful macOS desktop assistant named Gemini. You can see the user's \
screen (via screenshots with accessibility tree data) and hear them speak in real time.

ACTIVATION:
- The user activates you by saying "Hey Gemini" (or similar: "hey gemini", "ok gemini").
- ONLY respond when the user addresses you. Ignore background conversation, music, \
or speech not directed at you.
- Once activated, stay engaged for the current exchange until the task is done or \
the user stops talking to you. Then go back to waiting silently.

CAPABILITIES:
- See the user's screen and read UI elements from the accessibility tree
- Hear the user and respond with natural speech
- Perform desktop actions: click, type, scroll, open apps, use keyboard shortcuts

WHEN TO ACT vs. WHEN TO TALK:
- If the user asks you to DO something on their computer, use the available tools.
- If the user asks a QUESTION, just respond conversationally with your voice.
- After completing a task, briefly tell the user what you did.

COORDINATE SYSTEM:
- Coordinates are from the screenshot image (resized to 1280px wide).
- Use accessibility tree positions for precise clicks: click at (x + width/2, y + height/2).
- If the accessibility tree doesn't have the element, estimate from the screenshot.

RULES:
1. One action at a time. After each action, you will see an updated screenshot.
2. Verify your previous action succeeded before proceeding.
3. Never type passwords, credentials, or financial information.
4. For destructive actions (deleting files, sending messages), warn the user first.
5. If you can't find what you need, try scrolling or switching apps.
6. Be concise and natural in your spoken responses.
7. Always prefer open_app over Spotlight (Cmd+Space) for launching applications.
"""

CUA_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "click",
                "description": "Click at screen coordinates. Use accessibility tree positions for precision.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate (screenshot space)"},
                        "y": {"type": "integer", "description": "Y coordinate (screenshot space)"},
                        "button": {"type": "string", "description": "Mouse button", "enum": ["left", "right"]},
                    },
                    "required": ["x", "y"],
                },
            },
            {
                "name": "double_click",
                "description": "Double-click at screen coordinates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate"},
                        "y": {"type": "integer", "description": "Y coordinate"},
                    },
                    "required": ["x", "y"],
                },
            },
            {
                "name": "type_text",
                "description": "Type a string of text at the current cursor position.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "press_key",
                "description": "Press a key combo. Examples: return, tab, escape, Cmd+C, Cmd+V.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Key name: return, tab, escape, space, delete, a-z, 0-9, f1-f12, up, down, left, right",
                        },
                        "modifiers": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["command", "shift", "option", "control"]},
                            "description": "Modifier keys to hold",
                        },
                    },
                    "required": ["key"],
                },
            },
            {
                "name": "scroll",
                "description": "Scroll at the given position.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X coordinate"},
                        "y": {"type": "integer", "description": "Y coordinate"},
                        "direction": {"type": "string", "enum": ["up", "down"]},
                        "amount": {"type": "integer", "description": "Lines to scroll (default 3)"},
                    },
                    "required": ["x", "y", "direction"],
                },
            },
            {
                "name": "open_app",
                "description": "Open a macOS application by name. Always prefer this over Spotlight.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "App name (e.g. Safari, Google Chrome, Finder, Notes)",
                        },
                    },
                    "required": ["app_name"],
                },
            },
        ]
    }
]
