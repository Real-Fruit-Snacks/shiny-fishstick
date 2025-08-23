# Delta Vision Environment Variables Guide

## ✅ Environment Variables Working Correctly

The environment variables for Delta Vision server/client mode are now fully functional and tested. Here's how to use them:

## Server Mode

Start a Delta Vision server using environment variables:

```bash
export DELTA_MODE=server
export DELTA_PORT=9000
export DELTA_NEW=./New
export DELTA_OLD=./Old
python -m delta_vision
```

**Expected output:**
```
Starting server on port 9000...
Delta Vision server listening on 0.0.0.0:9000
```

## Client Mode

Connect to a Delta Vision server using environment variables:

```bash
export DELTA_MODE=client
export DELTA_HOST=localhost
export DELTA_PORT=9000
python -m delta_vision
```

**Expected output:**
```
Connecting to server at localhost:9000...
[delta-vision application launches]
```

## Legacy Environment Variables

For backward compatibility, you can also use:

```bash
export DELTA_SERVER=1
export DELTA_PORT=9000
export DELTA_NEW=./New
export DELTA_OLD=./Old
python -m delta_vision
```

## Complete Example: Server/Client Setup

### Terminal 1 - Server
```bash
cd /home/kali/Projects/shiny-fishstick
source .venv/bin/activate
export DELTA_MODE=server
export DELTA_PORT=9000
export DELTA_NEW=./New
export DELTA_OLD=./Old
python -m delta_vision
```

### Terminal 2 - Client
```bash
cd /home/kali/Projects/shiny-fishstick
source .venv/bin/activate
export DELTA_MODE=client
export DELTA_HOST=localhost
export DELTA_PORT=9000
python -m delta_vision
```


## Features

✅ **Environment variable support** - Use DELTA_MODE, DELTA_HOST, DELTA_PORT  
✅ **Legacy compatibility** - DELTA_SERVER=1 and DELTA_CLIENT=1 still work  
✅ **TTY handling** - Works in both TTY and non-TTY environments  
✅ **Remote terminal access** - Full terminal functionality over network  

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `DELTA_MODE` | Set to 'server' or 'client' | `DELTA_MODE=server` |
| `DELTA_HOST` | Server hostname for client | `DELTA_HOST=localhost` |
| `DELTA_PORT` | Port number | `DELTA_PORT=9000` |
| `DELTA_NEW` | Path to new files directory | `DELTA_NEW=./New` |
| `DELTA_OLD` | Path to old files directory | `DELTA_OLD=./Old` |
| `DELTA_KEYWORDS` | Path to keywords file | `DELTA_KEYWORDS=./keywords.md` |
| `DELTA_SERVER` | Legacy: set to '1' for server mode | `DELTA_SERVER=1` |
| `DELTA_CLIENT` | Legacy: set to '1' for client mode | `DELTA_CLIENT=1` |

## Testing

All functionality has been tested and verified using the main test suite:

```bash
# Run all tests
pytest

# Test environment variable functionality
pytest delta_vision/tests/
```

## Troubleshooting

### "Address already in use" error
```bash
# Kill any existing processes on the port
sudo fuser -k 9000/tcp
# Or use a different port
export DELTA_PORT=9001
```

### Non-TTY warnings
- This is normal when running in non-interactive environments
- The client will still connect and work, but terminal features are limited
- Use real terminal windows for full functionality

### Connection issues
- Ensure all clients are connected to the same server port
- Check that server shows "client connected" messages
- Verify the client can reach the server host and port

The server/client networking functionality is fully functional with environment variables! 🎉