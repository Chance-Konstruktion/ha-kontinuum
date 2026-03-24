# KONTINUUM

![KONTINUUM Logo](custom_components/kontinuum/assets/logo.png)

**Your home learns by itself.**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-0.17.0-blue)
![HA](https://img.shields.io/badge/Home%20Assistant-2024.1+-green)

> [Deutsche Version](README.md)

KONTINUUM is an experimental Home Assistant integration that understands your home without rules, without configuration, and without the cloud.

Instead of writing automations manually, KONTINUUM observes the continuous stream of events in your home, recognizes patterns in your behavior, and predicts what will happen next -- fully local and extremely resource-efficient.

The goal is radically simple:

**Install -- and forget. Your home learns the rest.**

---

## The Vision: Zero UI

Modern smart homes are often more complicated than life itself. You create automations, dashboards, scenes, rules, and scripts. In the end, you spend more time programming the house than living in it.

KONTINUUM pursues a different idea: **Zero UI**.

An intelligent home shouldn't need to be programmed. It should **understand**. You install the system -- and it begins to observe, learn, and understand.

---

## How It Works

```
Behavior flow --> Patterns --> Prediction --> Action
```

KONTINUUM observes the flow of events and recognizes recurring sequences. The house begins to understand:

- when you wake up
- which rooms you visit in sequence
- when you need the lights
- which routines repeat daily

**Your home isn't programmed -- it learns.**

### Example

A typical morning routine:

```
Bedroom door opened --> Motion in hallway --> Motion in kitchen --> Coffee machine
```

After this sequence has been observed frequently, KONTINUUM recognizes the pattern. Result: The coffee machine is prepared automatically, before you even think about it.

---

## Architecture: Inspired by the Human Brain

```
Thalamus --> Hippocampus --> Cerebellum --> PFC --> Action
    |             |              |           |
Hypothalamus   Spatial     Basal Ganglia  Amygdala
    |          Cortex      (Reward)
  Insula <-------+
                  |
            Cortex (optional, LLM Agents)
```

### Core Modules (always active, no LLM needed)

| Module | Function |
|--------|----------|
| **Thalamus** | Sensory gate -- filters events, recognizes rooms and semantics, knows sun position |
| **Hippocampus** | Memory -- learns sequences with N-gram Markov chains (1- to 4-grams), distinguishes weekday/weekend |
| **Hypothalamus** | Homeostasis -- monitors temperature, energy, and solar trends |
| **Spatial Cortex** | Spatial awareness -- analyzes movement, learns pathways, predicts next room |
| **Insula** | Body awareness -- recognizes modes (sleeping, active, relaxing, away), uses sun position |
| **Cerebellum** | Reflexes -- extracts stable routines as deterministic rules |
| **Basal Ganglia** | Reward learning -- Go/NoGo pathways, Q-values, habits |
| **Amygdala** | Risk assessment -- can veto actions before something unwanted happens |
| **Prefrontal Cortex** | Decision-making -- weighs predictions, evaluates benefit vs. risk |

### Cortex -- Conscious Thinking (optional, LLM Agents)

> **KONTINUUM works fully without LLM.** The Cortex is an optional upgrade for complex decisions. Core learning (patterns, routines, predictions) always runs locally without any cloud.

When enabled, up to **4 LLM Agents** can be configured:

| Role | Task |
|------|------|
| **Comfort** | Optimizes lighting, temperature, and ambiance |
| **Energy** | Monitors solar, battery, and consumption |
| **Safety** | Detects anomalies and has veto power |
| **Coordinator** | Sees all other agents' proposals and makes the final decision via LLM |
| **Custom** | Custom role with custom system prompt |

**Supported providers:** Ollama (local), OpenAI, Claude, Gemini, Grok -- all via pure HTTP (no SDK needed).

**How a Cortex consultation works:**

1. **Round 1** -- Worker agents (Comfort, Energy, Safety) think in parallel
2. **Round 2** -- If disagreement: agents see all proposals and can revise
3. **Decision** -- Coordinator decides via LLM, or algorithmic consensus (Veto > Unanimity > Majority > Priority)
4. **Safety veto always has absolute priority** -- even over the Coordinator

**Cortex Bridge:** LLM results flow back into the brain -- Hippocampus stores them as experience, Basal Ganglia learn from them, Amygdala evaluates risks, Cerebellum forms new reflexes. KONTINUUM becomes smarter long-term, even if the Cortex is later deactivated.

**Brain Review:** Monthly (or manually via service) all Cortex agents jointly analyze the brain state and deliver a health score with concrete improvement suggestions.

---

## Installation

### HACS (Custom Repository)

1. Open HACS --> Integrations --> Three-dot menu --> Custom Repositories
2. URL: `https://github.com/Chance-Konstruktion/ha-kontinuum`
3. Category: Integration
4. Install and restart

### Manual

1. Copy `custom_components/kontinuum/` to `/config/custom_components/kontinuum/`
2. Restart Home Assistant

### Setup

3. **Settings --> Integrations --> + Add --> KONTINUUM**
4. Choose a personality
5. Optional: Enable dashboard

KONTINUUM then starts learning automatically. **No further configuration needed.**

---

## Personality Presets

Choose how fast KONTINUUM learns during installation:

| Preset | Learning Speed | First Rules After | Error Tolerance |
|--------|---------------|-------------------|-----------------|
| **Bold** | Fast | ~1 day | High (learns from mistakes) |
| **Balanced** | Medium | ~3 days | Medium |
| **Conservative** | Slow | ~1 week | Low |

Can be changed later: Integrations --> KONTINUUM --> Configure

---

## Cortex (LLM Agents) Setup

> Optional -- KONTINUUM works fully without this step.

1. Integrations --> KONTINUUM --> Configure
2. Enable **Cortex**
3. Configure an agent:
   - Choose **Role** (Comfort / Energy / Safety / Coordinator / Custom)
   - Choose **Provider** (Ollama, OpenAI, Claude, Gemini, Grok)
   - Enter **URL** -- for Ollama just `localhost` or `192.168.1.100` is enough
4. Next step: **Select model**
   - For Ollama: all installed models shown as dropdown
   - For cloud providers: default model suggested
5. Optional: Add more agents (up to 4)

**Tip:** The 4th agent slot is ideal for the **Coordinator**, who acts as the "boss" deciding over the other 3 worker agents.

### Ollama Tips

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Download a model
ollama pull llama3.2

# List installed models
ollama list
```

---

## Dashboard

KONTINUUM includes an interactive brain visualization dashboard. When enabled during installation, it appears as a **sidebar entry** in Home Assistant:

- Sidebar --> **KONTINUUM** (Brain icon)
- Or directly: `/kontinuum`

### What does the dashboard show?

- **SVG brain map** with all 9 modules -- animated activation on events
- **Sensor panel** -- Last Event, Prediction, Accuracy, Energy in real-time
- **Context panel** -- current room, mode, cerebellum status
- **Module details** -- each brain module shows its statistics
- **Connection status** -- Green (connected), Red (error), Amber (connecting...)
- **Event log** -- live stream of recognized events with color coding

### Debug Panel

The dashboard has a built-in **debug mode** (toggle top right). It shows:

- **Cortex status** -- Agents, consultations, discussions, last consensus
- **Proposals and revisions** -- What each agent proposed in rounds 1 and 2
- **Brain Review** -- Health score and improvement suggestions

The debug panel provides **service trigger buttons** for direct interaction:

| Button | Service | What happens? |
|--------|---------|---------------|
| **Cortex Consult** | `kontinuum.cortex_consult` | Manually triggers a consultation of all Cortex agents. They analyze the current state and provide suggestions. Result as notification. |
| **Brain Review** | `kontinuum.brain_review` | All Cortex agents jointly analyze the brain state (patterns, accuracy, rules, habits). Returns health score + suggestions. |
| **Status** | `kontinuum.status` | Shows detailed KONTINUUM status as persistent_notification -- version, modules, statistics. |
| **Brain Export** | `kontinuum.export_brain` | Exports the compressed brain.json.gz as readable brain_export.json to /config/. For external analysis. |
| **Activate Light** | `kontinuum.activate` | Enables autonomous control for lights. KONTINUUM then controls lights based on learned patterns. |
| **Deactivate All** | `kontinuum.deactivate` | Disables autonomous control for all device types. KONTINUUM then only observes (shadow mode). |

---

## Sensors

KONTINUUM automatically creates native HA entities -- no YAML needed.

### System Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.kontinuum_status` | System status + version + all module statistics |
| `sensor.kontinuum_events` | Number of processed events |
| `sensor.kontinuum_accuracy` | Prediction accuracy (shadow mode hit rate) |
| `sensor.kontinuum_mode` | Current mode (sleeping, active, relaxing, ...) |
| `sensor.kontinuum_room` | Detected room |
| `sensor.kontinuum_location` | Location with presence map |
| `sensor.kontinuum_persons_home` | People at home |
| `sensor.kontinuum_prediction` | Current prediction + confidence |
| `sensor.kontinuum_energy` | Energy state + solar + trends |
| `sensor.kontinuum_cerebellum` | Learned routines (rule count, fired) |
| `sensor.kontinuum_basal_ganglia` | Habits + Go/NoGo + Q-values |
| `sensor.kontinuum_unknown_entities` | Entities without room assignment |

### Cortex Agent Sensors (only with Cortex enabled)

One sensor per configured agent:

| Sensor | Description |
|--------|-------------|
| `sensor.kontinuum_cortex_agent_1` | Agent 1 status (active/idle/error) |
| `sensor.kontinuum_cortex_agent_2` | Agent 2 status |
| `sensor.kontinuum_cortex_agent_3` | Agent 3 status |
| `sensor.kontinuum_cortex_agent_4` | Agent 4 status (e.g. Coordinator) |

Attributes per agent: `role`, `provider`, `model`, `total_calls`, `total_errors`, `error_rate`, `last_call`

### Activity Sensors (Dashboard Gauges)

Show the activity of each brain module (0.0 -- 1.0):

| Sensor | Module |
|--------|--------|
| `sensor.kontinuum_thalamus_activity` | Processing rate |
| `sensor.kontinuum_hippocampus_activity` | Learning accuracy |
| `sensor.kontinuum_hypothalamus_activity` | Energy trends |
| `sensor.kontinuum_amygdala_activity` | Risk level |
| `sensor.kontinuum_insula_activity` | Mode confidence |
| `sensor.kontinuum_cerebellum_activity` | Rule coverage |
| `sensor.kontinuum_prefrontal_activity` | Decision rate |
| `sensor.kontinuum_spatial_activity` | Room confidence |
| `sensor.kontinuum_basalganglia_activity` | Habit strength |

---

## Services

### Core Services (always available)

| Service | Description |
|---------|-------------|
| `kontinuum.status` | Show detailed status as notification |
| `kontinuum.export_brain` | Export brain as readable JSON (brain_export.json) |
| `kontinuum.activate` | Enable autonomous control for a device type (light, switch, fan, cover, climate, media, automation, vacuum) |
| `kontinuum.deactivate` | Disable autonomous control (per type or `all`) |
| `kontinuum.enable_scenes` | Enable automatic light scenes based on detected mode |
| `kontinuum.disable_scenes` | Disable light scenes |
| `kontinuum.set_scene` | Configure light scene per mode (brightness, color temperature) |

### Cortex Services (only with Cortex enabled)

| Service | Description |
|---------|-------------|
| `kontinuum.cortex_consult` | Manually trigger consultation of all Cortex agents |
| `kontinuum.brain_review` | Brain analysis by all agents (health score + suggestions) |
| `kontinuum.configure_agent` | Configure agent via service (slot 1-4) |
| `kontinuum.remove_agent` | Remove agent from slot |

---

## Events

| Event | Description |
|-------|-------------|
| `kontinuum_mode_changed` | Fires on mode change (old_mode, new_mode, confidence, room) |

Can be used for your own automations:

```yaml
trigger:
  platform: event
  event_type: kontinuum_mode_changed
  event_data:
    new_mode: sleeping
action:
  service: light.turn_off
  target:
    area_id: bedroom
```

---

## Technical Details

- **No ML, no deep learning** -- pure statistics (1- to 4-gram Markov chains)
- **Fully local** -- no cloud, no API calls (Cortex optional)
- **~6,000 lines of Python** -- runs on Raspberry Pi 4
- **21-dimensional context vector** -- time, sun position, energy, trends, mode
- **Adaptive context buckets** -- grows from 6 to 96 (time x mode x energy x day type)
- **Persistence** -- brain saved as compressed `brain.json.gz` (RPi SD-card friendly)
- **Shadow mode** -- observes and validates predictions before acting
- **Label support** -- HA labels usable as room hints
- **Clean uninstall** -- removes brain, helpers, and entities automatically
- **Cortex Bridge** -- LLM results flow back into the brain
- **Multi-agent discussion** -- agents discuss and find consensus
- **Coordinator agent** -- optional: 4th agent as LLM-based decision maker
- **Ollama Model Discovery** -- config flow auto-detects installed models

---

## Project Status

KONTINUUM is an experimental research project.

The goal is not just another smart home integration, but the exploration of a fundamental question:

> Can a home understand its residents without being programmed?

---

## Philosophy

> The best technology is the kind you don't notice.

When KONTINUUM works perfectly, something strange happens: you stop thinking about your smart home. It just works.

The way a home should.

---

**Learn one word. Your home learns the rest.**

*KONTINUUM*

---

## License

MIT License -- see [LICENSE](LICENSE)
