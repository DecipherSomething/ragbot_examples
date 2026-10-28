# OpenAI-Compatible Chat Interface

A simple, standalone HTML + JavaScript chat interface that connects to the RAG system's OpenAI-compatible API endpoint.

## Features

✨ **Key Features:**
- **Multi-turn Conversations** - Maintains conversation context across messages
- **Session Management** - Automatic session creation and continuity
- **Source Display** - Shows retrieved documents with relevance scores
- **Clean UI** - Modern, responsive design that works on all devices
- **Configuration** - Easy API URL and key management
- **Local Storage** - Saves your settings between sessions
- **CORS Compatible** - Works from any domain (perfect for hosting separately)

## Quick Start

### 1. Open the File

Simply open `index.html` in your web browser:

```bash
# From the examples/chat directory
open index.html

# Or use a simple HTTP server
python3 -m http.server 8000
# Then visit http://localhost:8000
```

### 2. Configure Settings

Click the **⚙️ Settings** button and configure:

- **API URL**: `https://demo.deciphersomething.com/api/v1/chat/completions` is pre-filled; change it to your own deployment's `/api/v1/chat/completions`
- **API Key**: Your API key (e.g., `sk_your_api_key_here`)
- **Model Name**: `rag-model` (or your model identifier)

Settings are automatically saved to localStorage.

### 3. Start Chatting!

Type your message and press **Enter** (or click **Send**) to start a conversation.

## Usage Examples

### Basic Conversation

```
You: What is RAG?
Assistant: RAG stands for Retrieval-Augmented Generation...
[Shows relevant sources]

You: Tell me more about the retrieval process
Assistant: The retrieval process works by...
[Context maintained from previous message]
```

### Multi-turn Context

The chat automatically maintains session context across messages:
- First message creates a new session
- Subsequent messages use the same session
- Click **+ New Chat** to start fresh

## API Integration

The chat interface uses the OpenAI-compatible Chat Completions API:

### Request Format

```javascript
{
  "model": "rag-model",
  "messages": [
    {"role": "user", "content": "What is RAG?"},
    {"role": "assistant", "content": "RAG stands for..."},
    {"role": "user", "content": "Tell me more"}
  ],
  "rag_options": {
    "session_guid": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Response Format

```javascript
{
  "id": "chatcmpl-abc123...",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "rag-model",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "RAG stands for..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 42,
    "total_tokens": 57
  },
  "sources": [...],
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Deployment

### Option 1: Static Hosting

Host the `index.html` file on any static hosting service:

- **GitHub Pages**: Commit to repo, enable Pages
- **Netlify**: Drag and drop the file
- **Vercel**: Deploy with a single command
- **S3 + CloudFront**: Upload to S3 bucket

### Option 2: Embed in Website

```html
<iframe
  src="https://your-site.com/chat/index.html"
  width="100%"
  height="600px"
  style="border: none; border-radius: 12px;">
</iframe>
```

### Option 3: Local File

Just open the HTML file directly - no server needed!

## CORS Configuration

The ragBot server already has CORS enabled in its FastAPI app:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production Note**: Restrict `allow_origins` to specific domains for security.

## Customization

### Change Colors

Edit the CSS gradient in `<style>`:

```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

### Add Features

The JavaScript is well-commented and easy to extend:

- **Add streaming**: Implement SSE or WebSocket support
- **Add file uploads**: Extend the input area
- **Add voice input**: Use Web Speech API
- **Add themes**: Implement dark mode toggle

### Modify UI

The HTML structure is semantic and easy to modify:

```html
<div class="container">
  <div class="header">...</div>
  <div class="config-panel">...</div>
  <div class="session-info">...</div>
  <div class="chat-messages">...</div>
  <div class="input-area">...</div>
</div>
```

## Keyboard Shortcuts

- **Enter**: Send message
- **Shift+Enter**: New line in message
- **+ New Chat** button: start a fresh session

## Browser Compatibility

Works in all modern browsers:
- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

## Troubleshooting

### CORS Errors

If you see CORS errors in the browser console:

1. Ensure the API server has CORS enabled (it should be)
2. Check the API URL is correct
3. For local development, run from `http://localhost` not `file://`

### Authentication Errors

If you get 401/403 errors:

1. Check your API key is correct
2. Ensure the API key has proper permissions
3. Check the Authorization header is being sent

### Connection Errors

If the chat can't connect:

1. Verify the API URL is accessible
2. Check the server is running
3. Open browser DevTools → Network tab to see the actual request

### Messages Not Showing

1. Check browser console for JavaScript errors
2. Ensure the API response format is correct
3. Try clearing localStorage and reloading

## Security Notes

⚠️ **Important Security Considerations:**

1. **API Keys**: Stored in localStorage (not encrypted)
   - Don't use this for production with sensitive keys
   - Consider server-side proxy for production

2. **CORS**: Currently allows all origins
   - Restrict in production to specific domains

3. **HTTPS**: Use HTTPS in production
   - Required for secure API key transmission

4. **Content Security**: No XSS protection built-in
   - Consider adding CSP headers if hosting

## Example Deployment: GitHub Pages

1. **Create a new repository**
2. **Add the file**:
   ```bash
   git clone https://github.com/yourusername/rag-chat.git
   cd rag-chat
   cp /path/to/index.html .
   git add index.html
   git commit -m "Add chat interface"
   git push
   ```
3. **Enable GitHub Pages**:
   - Go to Settings → Pages
   - Select branch: main
   - Select folder: / (root)
   - Save
4. **Access**: `https://yourusername.github.io/rag-chat/`

## Support

For issues or questions:
- Check the main RAG system documentation
- Review the API endpoint documentation
- Open an issue on the project repository

## License

Same as the ragBot Platform.
