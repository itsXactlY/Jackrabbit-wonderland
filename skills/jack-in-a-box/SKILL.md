---
name: jack-in-a-box
category: devops
description: All-in-one Hermes stack installer - hermes+neural+pulse+crypto from one command
tags: [installer, hermes, neural-memory, pulse, crypto, deployment]
---

# Jack-in-a-Box
One command. Everything springs to life.

## Overview
Jack-in-a-Box is a unified installer for the complete Hermes ecosystem. It deploys all core components in a single operation, eliminating the need for manual setup of individual repositories and dependencies.

## Components
| Component | Repo | Purpose |
|-----------|------|---------|
| Hermes Agent | itsXactlY/hermes-agent (dev/unified) | AI agent framework |
| Neural Memory | itsXactlY/neural-memory | Local semantic memory |
| PULSE | itsXactlY/pulse-hermes | Social search engine (15+ sources) |
| Jackrabbit Wonderland | itsXactlY/Jackrabbit-wonderland | AES256 crypto |
| JackrabbitDLM | rapmd73/JackrabbitDLM | Volatile key vault (port 37373) |

## Install Modes
- **Full**: `bash install.sh` - Installs all components
- **Lite (no crypto)**: `bash install.sh --lite` - Excludes crypto components
- **Selective**: `bash install.sh --components hermes,neural,pulse` - Install specific components only

## Prerequisites
- Linux/macOS system
- Git installed
- Python 3.10+ with pip
- Node.js 18+ (for some components)
- 4GB+ RAM recommended
- 10GB+ disk space for full installation

## Installation Steps

### 1. Download Installer
```bash
git clone https://github.com/itsXactlY/jack-in-a-box.git
cd jack-in-a-box
```

### 2. Run Full Installation
```bash
# Full installation with all components
bash install.sh

# Or with specific options
bash install.sh --lite  # No crypto components
bash install.sh --components hermes,neural,pulse  # Selective
```

### 3. Post-Installation Configuration
After installation, configure each component:

#### Hermes Agent Configuration
```bash
cd ~/hermes-agent
cp .env.example .env
# Edit .env with your API keys and settings
```

#### Neural Memory Setup
```bash
cd ~/neural-memory
python -m pip install -r requirements.txt
# Initialize database
python init_db.py
```

#### PULSE Configuration
```bash
cd ~/pulse-hermes
# Configure social media API keys in config.yaml
```

#### Crypto Setup (if installed)
```bash
cd ~/Jackrabbit-wonderland
# Generate encryption keys
python generate_keys.py
```

## Directory Structure
```
~/hermes-stack/
├── hermes-agent/          # Core AI agent
├── neural-memory/         # Semantic memory system
├── pulse-hermes/          # Social search engine
├── Jackrabbit-wonderland/ # AES256 crypto
├── JackrabbitDLM/         # Key vault service
└── shared/                # Shared configs and utilities
```

## Verification

### Check Installation Status
```bash
# Verify all components are present
ls -la ~/hermes-stack/

# Test Hermes Agent
cd ~/hermes-agent
python -c "import hermes; print('Hermes OK')"

# Test Neural Memory
cd ~/neural-memory
python test_connection.py

# Test PULSE
cd ~/pulse-hermes
python -c "import pulse; print('PULSE OK')"

# Test Crypto (if installed)
cd ~/Jackrabbit-wonderland
python -c "import jackrabbit; print('Jackrabbit OK')"
```

### Start Services
```bash
# Start Hermes Gateway
cd ~/hermes-agent
python gateway.py

# Start JackrabbitDLM (port 37373)
cd ~/JackrabbitDLM
python dlm_server.py

# Start PULSE API
cd ~/pulse-hermes
python api_server.py
```

## Common Issues

### Missing Dependencies
**Problem**: ModuleNotFoundError for various packages
**Solution**: 
```bash
cd ~/hermes-stack
find . -name "requirements.txt" -exec pip install -r {} \;
```

### Port Conflicts
**Problem**: JackrabbitDLM port 37373 already in use
**Solution**: Check for existing processes: `lsof -i :37373` or change port in config

### Permission Errors
**Problem**: Permission denied when writing to directories
**Solution**: 
```bash
sudo chown -R $USER:$USER ~/hermes-stack
chmod -R 755 ~/hermes-stack
```

### Python Version Conflicts
**Problem**: Some components require Python 3.10+, system has older version
**Solution**: Use pyenv or conda to manage Python versions:
```bash
pyenv install 3.10.0
pyenv local 3.10.0
```

## Advanced Configuration

### Custom Installation Path
```bash
# Install to custom directory
bash install.sh --install-dir /opt/hermes-stack
```

### Component Versions
```bash
# Install specific versions
bash install.sh --hermes-version v2.1.0 --neural-version v1.3.2
```

### Development Mode
```bash
# Install in development mode with symlinks
bash install.sh --dev
```

## Integration Testing
```bash
# Run integration tests
cd ~/hermes-stack
python run_integration_tests.py

# Test component communication
python test_component_communication.py
```

## Troubleshooting

### Logs Location
- Installation logs: `~/hermes-stack/logs/install.log`
- Component logs: `~/hermes-stack/logs/<component>.log`
- System logs: `/var/log/hermes-stack.log`

### Reset Installation
```bash
# Complete reset (WARNING: deletes all data)
bash install.sh --reset

# Reset specific component
bash install.sh --reset-component neural-memory
```

### Update Components
```bash
# Update all components
bash install.sh --update

# Update specific component
bash install.sh --update-component hermes-agent
```

## Security Considerations
- Crypto components handle sensitive encryption keys
- Ensure proper file permissions (600 for key files)
- Use environment variables for API keys, not hardcoded values
- Regular security updates recommended
- Consider network isolation for production deployments

## Performance Tuning
- Neural Memory: Adjust embedding batch size based on RAM
- PULSE: Configure rate limits for social media APIs
- Hermes Agent: Tune model parameters for your hardware
- JackrabbitDLM: Adjust vault size and cleanup intervals

## Support
- GitHub Issues: https://github.com/itsXactlY/jack-in-a-box/issues
- Documentation: https://github.com/itsXactlY/jack-in-a-box/wiki
- Community: https://discord.gg/hermes-stack