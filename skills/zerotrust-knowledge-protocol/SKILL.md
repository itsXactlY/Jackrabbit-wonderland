# Zero Trust Knowledge Protocol for Key Exchanges

## Category
security

## Description
Implements a complete Zero Trust Knowledge protocol for secure key exchanges in the DayZ PBO obfuscation system using AES-GCM 256-bit encryption. This protocol ensures that cryptographic keys are never exposed, all communications are authenticated and encrypted, and replay attacks are prevented through proper IV management.

## Details
This skill provides military-grade security for the DayZ PBO obfuscation system while maintaining compatibility with existing systems and following the "how to code properly" principles from LBMaster through proper separation of concerns, component-based design, and rigorous security practices.

### Key Features
- AES-GCM 256-bit authenticated encryption
- X25519 elliptic curve Diffie-Hellman key exchange
- HMAC-SHA3-256 for authentication
- HKDF-SHA3-256 for key derivation
- Per-message unique IVs to prevent replay attacks
- Hardware-backed secure key storage when available
- Fail-secure default posture
- Forward and future secrecy

### Integration Points
- Integrates with existing VPP3DMarker.c and related 3D marker systems
- Enhances PBO obfuscation system with secure parameter exchange
- Compatible with existing ModdedClasses menu systems
- Works with GroupHUD and EnhancedCompass systems

### Files Modified
- Creates new security module in /src/crypto/protocols/ZeroTrustKnowledgeProtocol.*
- Enhances existing marker systems with secure initialization
- Maintains backward compatibility through fallback mechanism

### Usage
Enable via VPPMAP_ZTK_ENABLED=1 in configuration
Automatically used by marker systems when establishing secure connections

## Licensing
MIT License - See /home/alca/.hermes/your-workspace/skills/zerotrust-knowledge-protocol/License.txt for details