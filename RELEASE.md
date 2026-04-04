## Release v0.4.0 - VM Network Isolation & VLAN Support 🌐

**Release Date:** 2026-04-04

### 🎉 What's New in UpservX v0.4.0

This release extends the virtual machine networking stack with two new capabilities: VLAN tagging for bridge-mode interfaces and full lifecycle management of isolated internal libvirt networks — enabling air-gapped VM communication with no IP configuration on the host side.

### ✨ Highlights

#### 🔖 VLAN Support for VMs
- Bridge-mode VM interfaces now support optional VLAN tagging (802.1Q)
- Specify a VLAN ID (1–4094) when creating, editing or importing a VM
- A tagged sub-interface (e.g. `eth0.100`) is created automatically on the host if it does not yet exist
- VLAN ID stored in the VM registry and restored on edit

#### 🔒 Internal VM Networks
- New **Internal Network** mode alongside NAT, Bridge and None
- Create isolated L2 libvirt networks with a name — no subnet, no DHCP, no host routing
- All IP addressing happens inside the VMs themselves; the host gains no route
- Full network lifecycle: create, start, stop and delete via the new **Manage Networks** dialog in the VM dashboard
- Network state (active / inactive) shown in the networks table with one-click start/stop toggles
- New API endpoints: `GET /vm-networks`, `POST /vm-networks`, `DELETE /vm-networks/{name}`, `POST /vm-networks/{name}/start`, `POST /vm-networks/{name}/stop`

#### 🖥️ CLI Version Bump
- `upservx` CLI updated to v0.4.0
- All existing commands remain unchanged: `auth`, `service`, `containers`, `system`, `apps`, `backup`, `logs`

### 📄 Full Release Notes
See [releases/0.4.0.md](releases/0.4.0.md) for complete details including all API changes and upgrade notes.