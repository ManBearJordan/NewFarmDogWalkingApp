# New Farm Dog Walking — Desktop App

## Secure Stripe Key Management with GUI Setup

The app now features a **user-friendly GUI prompt** for initial Stripe secret key setup, combined with secure storage in your system's credential manager.

### 🔐 Security Features

- **Secure Storage**: Keys stored in system credential manager
  - Windows: Windows Credential Manager  
  - macOS: Keychain
  - Linux: Secret Service (GNOME Keyring, KDE KWallet)
- **Never Plaintext**: Keys are never stored in files or committed to version control
- **Cross-Platform**: Designed for future server/mobile integration

### 🖥️ GUI Setup (NEW!)

On first run, the app shows a **friendly dialog box** to collect your Stripe secret key:

1. **Information Dialog**: Clear instructions on where to find your Stripe key
2. **Secure Input**: Password-style input field that hides your key as you type
3. **Automatic Storage**: Key is stored securely in your system's credential manager
4. **One-Time Setup**: Subsequent runs retrieve the key automatically

#### Finding Your Stripe Secret Key

1. Log in to your [Stripe Dashboard](https://dashboard.stripe.com/)
2. Go to **Developers** > **API keys**
3. Copy the **Secret key** (starts with `sk_test_` or `sk_live_`)

**For development**: Use a test key (`sk_test_...`)  
**For production**: Use a live key (`sk_live_...`)

### 🔄 Fallback Options

The app gracefully handles different environments:

- **Desktop with GUI**: Shows user-friendly dialog boxes
- **Headless/Server**: Falls back to console prompts automatically
- **Command Line**: `python stripe_key_manager.py set`
- **Environment Variables**: `STRIPE_SECRET_KEY=your_key_here`

### 📋 Requirements

The following dependencies are included in `requirements.txt`:

```text
keyring>=25.6.0    # Secure credential storage
stripe>=12.5.1     # Stripe API integration
# tkinter is included with Python (no separate install needed)
```

### 🚀 Quick Start

1. **Run the app**: `Start-App.bat` (Windows) or `python app.py`
2. **GUI Setup**: Follow the dialog prompts to enter your Stripe key
3. **Done**: Key is stored securely and retrieved automatically on future runs

### 🔧 Advanced Usage

#### Check Key Status
```bash
python stripe_key_manager.py status
```

#### Manual Key Setup (Command Line)
```bash
python stripe_key_manager.py set
```

#### Remove Stored Key
```bash
python stripe_key_manager.py delete
```

### 🔍 Status Information

The key manager provides detailed status information:

- **Key Storage**: Whether a key is currently stored
- **Key Type**: Test (`sk_test_`) or Live (`sk_live_`)
- **Keyring Available**: Whether secure storage is working
- **GUI Available**: Whether GUI prompts are supported
- **Storage Method**: `keyring` or `environment_variables`

### 🌐 Cross-Platform Compatibility

The implementation is designed for seamless migration:

- **Current**: Desktop app with Windows Credential Manager
- **Future**: Server deployment with environment variables
- **Future**: Mobile app integration with platform-specific secure storage

### 📊 Legacy Support

The previous setup methods still work but are less secure:

1. Copy `secrets_config.example.py` to `secrets_config.py`
2. Edit `secrets_config.py` with your actual key
3. **⚠️ Never commit `secrets_config.py` to version control**

### 🛡️ Security Benefits

| Feature | GUI + Keyring | Environment Variables | File-based |
|---------|:-------------:|:---------------------:|:----------:|
| Encrypted Storage | ✅ | ❌ | ❌ |
| User-Friendly Setup | ✅ | ❌ | ❌ |
| No Accidental Commits | ✅ | ✅ | ⚠️ |
| Cross-Platform Ready | ✅ | ✅ | ❌ |
| Server Compatible | ✅ | ✅ | ❌ |

---

**Next Steps**: Continue with normal app usage. The Stripe key will be retrieved securely in the background for all payment processing.