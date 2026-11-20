# Jeff VPN controls

Jeff can list and control OpenVPN Connect profiles that macOS has registered as
VPN services. The first integration targets OpenVPN Connect on macOS; it does
not install a VPN client, import profiles, or store Proton credentials.

## One-time setup

1. Install and sign in to OpenVPN Connect, then import the provider's `.ovpn`
   profiles.
2. Approve OpenVPN Connect's Network Extension and VPN configuration prompts
   in macOS if they appear.
3. Confirm the profiles appear under **System Settings → VPN**.
4. Start Jeff and open **VPN location**. Jeff lists profiles that macOS exposes
   as OpenVPN Connect services.

OpenVPN Connect 3.9 and later uses Apple's Network Extension framework and
registers connection profiles with macOS. Jeff uses `scutil --nc` to list,
check, start, and stop only those OpenVPN Connect services. Other VPN providers
and unrelated network services are not controlled. See [OpenVPN's macOS Network
Extension guide](https://openvpn.net/connect-docs/macos-network-extension/).

## Chat commands and confirmation

Jeff recognizes explicit requests such as **“Change my VPN location to Japan”**,
**“Connect to Canada”**, or **“Disconnect VPN”**. It does not ask Ollama to
interpret these commands. Jeff displays the matching registered profile and
waits for a Connect or Disconnect click before changing the system VPN. Cancel
leaves the connection unchanged. If a profile is not found or macOS reports
another VPN connected, Jeff explains what to do.

The VPN page also provides direct controls for each profile. Jeff does not
receive, save, or pass OpenVPN usernames or passwords. Commands are invoked as
argument arrays without a shell; service identifiers are validated against the
current macOS list before use.

## What the location change means

An OpenVPN connection routes network traffic for the Mac, not only Firefox.
After connecting, reload the webpage. The VPN can change IP-derived location,
but a site may use browser geolocation permissions, account details, cookies,
timezone, or other signals. Jeff does not change those signals and does not
promise that a site will use the VPN's IP location.

The VPN provider sees traffic routed through its servers. Jeff does not send
chat messages or page text to the VPN service. The browser page and Firefox
companion continue to use their existing Ollama and local-bridge behavior.

## Troubleshooting

- If Jeff finds no profiles, open OpenVPN Connect and approve its VPN prompts;
  then check **System Settings → VPN** and refresh Jeff's VPN page.
- If a profile fails to connect, check its status in OpenVPN Connect or System
  Settings. Jeff retains the original command error under **Technical details**.
- Jeff currently recognizes the saved Japan, Canada, and United States profile
  labels for chat requests. The VPN page lists other registered OpenVPN
  profiles too, with a generic label if it cannot identify their country.
- On non-macOS systems, Jeff reports that built-in VPN controls are unavailable.

## Verification and manual checks

Automated tests mock `scutil`; they do not start or stop the real VPN. Check the
VPN page, connect to a profile, verify the active status in macOS, reload a
website and inspect its IP-based location, then disconnect from Jeff. Also
check that Cancel does not change the connection and that a second profile is
not started while one is already connected.
