# Handoff: KaiserClaim — Mobile-First Health Insurance Reimbursement App

## Overview

KaiserClaim automates Austrian health insurance reimbursements. A user photographs a medical or pharmacy receipt, the app extracts amount and date via OCR, submits claims to both **ÖGK** (public insurer) and **Merkur** (private insurer) on their behalf, tracks the refund pipeline, and shows how much of each benefit quota is left — for all family members under one contract.

**Target platform:** Mobile-first web app (PWA). Primary viewport: 390–430 px wide. Also works on desktop (centered, max-width 430 px, letterboxed).

**Language:** Austrian German (de-AT). Currency: EUR with `€\u2009` prefix (thin space). Dates: DD.MM.YYYY.

---

## About the Design Files

The files in this bundle (`KaiserClaim.html`, `kc-*.jsx`) are **high-fidelity design prototypes** built in plain React + Babel — not production code. They are fully interactive and demonstrate exact intended look, layout, copy, and behaviour.

**Your task:** Recreate these designs in your target codebase using its established framework, routing, component library, and state management patterns. Do not ship the prototype HTML directly. Use the prototype as a pixel-accurate visual reference and this README as your implementation specification.

---

## Fidelity

**High-fidelity.** Final colors, typography, spacing, copy, icons, and interactions are all specified. Recreate pixel-accurately. Where your design system conflicts, prefer the values in this document.

---

## Design Tokens

### Colors

```js
// Backgrounds
bg:           '#F8F7F4'   // warm off-white page background
surface:      '#FFFFFF'   // card / sheet surface
surfaceAlt:   '#F2F1EE'   // input backgrounds, secondary fills
border:       '#E5E3DE'   // card borders
borderLight:  '#EEEDEA'   // dividers inside cards

// Text
text:         '#1A1F36'   // primary text
textSec:      '#6B7280'   // secondary / labels
textTri:      '#9CA3AF'   // tertiary / placeholders
textInv:      '#FFFFFF'   // text on dark surfaces

// Brand
brand:        '#1A1F36'   // wordmark, hero gradient start
accent:       '#0D9488'   // teal — CTAs, links, active states
accentHover:  '#0F766E'
accentLight:  '#F0FDFA'   // accent tinted background
accentMid:    '#CCFBF1'   // accent icon background

// Semantic
danger:       '#DC2626'
dangerBg:     '#FEF2F2'

// Dark mode equivalents
darkBg:       '#111318'
darkSurface:  '#1A1D25'
darkSurfaceAlt:'#22252E'
darkBorder:   '#2E313A'
darkText:     '#E8E9EC'
darkTextSec:  '#9CA3AF'
```

### Status Pill Colors

| Status key         | Label                    | Text      | Background |
|--------------------|--------------------------|-----------|------------|
| `empfangen`        | Empfangen                | `#6B7280` | `#F3F4F6`  |
| `ocr`              | OCR-Verarbeitung         | `#A16207` | `#FEF9C3`  |
| `bereit_oegk`      | Bereit für ÖGK          | `#2563EB` | `#DBEAFE`  |
| `bei_oegk`         | Bei ÖGK eingereicht     | `#1D4ED8` | `#DBEAFE`  |
| `von_oegk`         | Von ÖGK erstattet        | `#4338CA` | `#E0E7FF`  |
| `bereit_merkur`    | Bereit für Merkur        | `#C2410C` | `#FFEDD5`  |
| `bei_merkur`       | Bei Merkur eingereicht   | `#6D28D9` | `#EDE9FE`  |
| `abgeschlossen`    | Abgeschlossen            | `#15803D` | `#DCFCE7`  |

### Typography

**Font family:** `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif`  
Load from Google Fonts: `https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap`

| Role             | Size  | Weight | Letter-spacing |
|------------------|-------|--------|----------------|
| Hero number      | 44px  | 700    | -0.02em        |
| Page title       | 22px  | 700    | —              |
| Section title    | 17px  | 700    | —              |
| Card title       | 15px  | 600    | —              |
| Body             | 14px  | 400/500| —              |
| Label / caption  | 13px  | 500–600| —              |
| Small / pill     | 11–12px| 600   | 0.01–0.02em    |

Use `font-variant-numeric: tabular-nums` on all monetary and numeric values.

### Spacing & Radius

```
Radius:  sm=8  md=12  lg=16  xl=20  pill=9999
Gap:     xs=6  sm=8   md=12  lg=16  xl=20  xxl=24
```

### Shadows

```css
--shadow-sm:   0 1px 3px rgba(0,0,0,0.04);
--shadow-md:   0 2px 8px rgba(0,0,0,0.06);
--shadow-lg:   0 4px 16px rgba(0,0,0,0.08);
--shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
```

### Family Member Colors

```js
maria:  '#E84393'  // pink
thomas: '#3B82F6'  // blue
luisa:  '#F59E0B'  // amber
felix:  '#10B981'  // emerald
```

---

## App Shell

### Layout

```
┌──────────────────┐
│  TopBar (56px)   │  sticky top, z-index 100
├──────────────────┤
│                  │
│   Screen         │  flex: 1, overflow-y: auto
│   (scrollable)   │
│                  │
├──────────────────┤
│  BottomNav (64px)│  sticky bottom, z-index 100
└──────────────────┘
```

Max-width: 430px, centered. On screens wider than 430px, show rounded card (border-radius 24px) on a `#E8E7E4` background.

### TopBar

- Height: 56px, `padding: 0 20px`
- Left: logo (28×28 teal shield icon + wordmark "Kaiser**Claim**" — "Kaiser" weight 700, "Claim" weight 500, size 18px, letter-spacing -0.02em) **or** back button (`←  Zurück`, accent color, 14px weight 500)
- Center: screen title (only shown on sub-screens, 15px weight 600)
- Right: settings icon (22px) **or** spacer div

### BottomNav

5 items, `justify-content: space-around`, height 64px.

| Position | Tab ID     | Icon      | Label      |
|----------|------------|-----------|------------|
| 1        | `home`     | home      | Übersicht  |
| 2        | `invoices` | receipt   | Belege     |
| 3        | — (FAB)    | plus      | —          |
| 4        | `benefits` | barChart  | Leistungen |
| 5        | `stats`    | trending  | Statistik  |

The center item is a **floating action button**: 48×48px, border-radius 14px, teal background, `-12px` top margin (pops above the nav bar), box-shadow `0 4px 12px #0D948844`. Navigates to the Upload screen.

Active tab: accent color icon + label. Inactive: `#9CA3AF`.

---

## Screens

### 1. Login / Auth

**Route:** `/login`  
**Sub-screens with back nav:** No  

**Layout (vertically centered, padding 40px 24px):**
- Logo: 64×64px teal rounded square (radius 20), shield icon (32px white), box-shadow `0 8px 24px #0D948833`
- Title: "KaiserClaim" — 28px, weight 700, letter-spacing -0.02em
- Subtitle: "Ihre Gesundheitskosten. Automatisch erstattet." — 15px, textSec, centered, line-height 1.5
- Card (radius 16, padding 24):
  - Email input (label "E-Mail-Adresse", placeholder "name@beispiel.at", type email, left icon: mail)
  - Primary CTA button full-width, height 52px: "Anmelden"
- Trust line (centered, 12px textTri): lock icon + "Ende-zu-Ende verschlüsselt · DSGVO-konform"

**Validation:** Show inline error "Bitte gültige E-Mail-Adresse eingeben" if `@` missing on submit.  
**Loading state:** Spinner replaces button icon for ~1.2s, then navigate to Home.

---

### 2. Home / Übersicht

**Route:** `/`  
**Has family filter:** Yes (top, horizontal scroll pills)

**Layout:**
1. **Family filter pills** — `padding: 16px 20px`, horizontal scroll, no scrollbar visible
2. **Hero financial card** — `margin: 0 20px 16px`, gradient background `linear-gradient(135deg, #1A1F36 0%, #2D3A5E 100%)`, radius 20px, padding 24px 20px, overflow hidden. Contains:
   - Label: "Gesamtausgaben 2026" (+ member name if filtered), 12px, `rgba(255,255,255,0.6)`
   - Hero amount: `€\u2009X.XXX,XX` — 44px, weight 700, white, letter-spacing -0.02em, animated count-up on mount
   - 3 stat chips (10px opacity background `rgba(255,255,255,0.1)`, radius 12, padding 8px 12px, flex: 1):
     - "Erstattet" — amount in €
     - "In Bearbeitung" — count
     - "Eigenanteil" — amount in €
   - Decorative circles: top-right 120px circle `rgba(255,255,255,0.05)`, bottom-right 80px circle `rgba(255,255,255,0.03)`
3. **Upload CTA** — Full-width teal button, height 52px, upload icon + "Beleg hochladen", `margin: 0 20px 20px`
4. **Benefit alerts** (if any benefit ≥75%): amber `#FFF7ED` background cards, `margin: 0 20px 16px`, alertCircle icon, text "{MemberName}: {BenefitName} — X% ausgeschöpft"
5. **Stats teaser card** — `margin: 0 20px 20px`, hover card with trending icon, "Statistiken ansehen", subtitle "Monatliche Ausgaben & Erstattungen"
6. **Section header** "Letzte Belege" + "Alle anzeigen" link, then invoice cards (see Invoice Card component)

**Financial calculation:**
- `totalPaid = sum(filtered invoices, amount)`
- `totalReimbursed = sum(completed invoices, amount) × 0.82` (82% reimbursement rate)
- `inProgress = invoices where status ≠ 'abgeschlossen'`
- `eigenanteil = totalPaid - totalReimbursed`

---

### 3. Beleg hochladen / Upload

**Route:** `/upload`  
**Back nav:** Yes — "Zurück"

**Layout:**
- Title "Beleg hochladen" (22px bold) + subtitle
- **Drop zone** (see component below)
- If PDF selected: file name row with file icon + filename + × button
- **Familienmitglied** select (person picker, optional)
- **Vertrag** select: "Merkur Sonderklasse — MS-2024-78912", "ÖGK — Pflichtversicherung"
- **Leistung** select: Zahnreinigung, Physiotherapie, Allgemeinmedizin, Medikamente, Sehbehelfe, Kinderarzt (with limits)
- Inline error row (red background, alertCircle icon)
- **Upload button** full-width height 52px (shows spinner during upload)

**Success state (replaces content):**
- Centered: 72×72 green circle (radius 36, `#DCFCE7` bg), checkCircle icon 36px `#16A34A`, animation `kcPop` (scale 0.5→1.1→1)
- "Beleg hochgeladen" 20px bold
- "Ihr Beleg wird jetzt verarbeitet." 14px secondary
- Auto-navigate to Belege after 1.5s

---

### 4. Belege / Invoice List

**Route:** `/invoices`  
**Has family filter:** Yes

**Layout:**
- Family filter pills (top)
- Title "Belege" + optional member name suffix
- Search bar (surfaceAlt background, search icon, placeholder "Belege durchsuchen...")
- Status filter tabs: "Alle" | "Laufend" | "Fertig" — pill style, active = brand dark bg + white text
- Invoice cards list (see Invoice Card component)

**Empty state:** receipt icon, "Keine Belege gefunden", contextual message

---

### 5. Beleg-Detail / Invoice Detail

**Route:** `/invoices/:id`  
**Back nav:** Yes — "Belegdetails"

**Layout:**
1. **Summary card** (radius 16, overflow hidden):
   - Header strip: surface-alt bg, "Belegdetails" + status pill
   - Detail rows (with dividers):  Betrag · Datum · Anbieter · Patient · Kategorie · Vertrag · Hochgeladen am
2. **Contextual action button** (only when `status === 'von_oegk'` or `'bereit_merkur'`): full-width teal, send icon + "An Merkur übermitteln"
3. **Pipeline card**: "Erstattungs-Pipeline" title + pipeline type badge (Apotheke vs. Standardweg)
   - Vertical stepper (see component)

**Pipeline variants:**

Standard path (8 steps):
`empfangen → ocr → bereit_oegk → bei_oegk → von_oegk → bereit_merkur → bei_merkur → abgeschlossen`

Pharmacy path (5 steps):
`empfangen → ocr → bereit_merkur → bei_merkur → abgeschlossen`

---

### 6. Leistungen / Benefits Dashboard

**Route:** `/benefits`  
**Has family filter:** Yes

**Layout:**
- Family filter pills
- Title "Leistungen" + subtitle (member name or "Alle Familienmitglieder")
- "Vertrag hinzufügen" secondary button (top right)
- Per contract:
  - **Contract header** (radius 16 top only): shield icon in teal tinted box, contract name + policy number
  - Per family member (filtered by active member):
    - Member row: avatar + name, surfaceAlt background
    - Per benefit: name + period badge + progress bar
  - Card bottom radius 16

**Progress bar color logic:**
- `< 75%`: `#16A34A` green
- `≥ 75%`: `#F59E0B` amber
- `≥ 100%`: `#DC2626` red

Label below bar: "€ X übrig" (colored) + "€ used / € limit" (tertiary, right-aligned)

---

### 7. Statistiken / Statistics

**Route:** `/stats`  
**Has family filter:** Yes

**Layout:**
- Family filter pills
- Title "Statistiken" + year badge
- **4 stat cards** in 2×2 grid:
  - Ausgaben (neutral)
  - Erstattet (green `#16A34A`)
  - Eigenanteil (orange `#EA580C`)
  - Erstattungsquote % (accent)
- **View tabs:** "Monatlich" | "Jährlich" | "Mitglieder"

**Monatlich view:**
- Bar chart (height 160px): 5 months Jan–Mai 2026, stacked by member (when "Alle"), single color (member color) when filtered
- Monthly breakdown table: month name + formatted amount

**Jährlich view:**
- Bar chart (3 bars: 2024, 2025, 2026)
- Year cards: Ausgaben + Erstattet + Eigenanteil per year

**Mitglieder view:**
- Per-member card: avatar + name + Belege count
  - 3 figures: Ausgaben / Erstattet / Eigenanteil
  - Mini share bar (member color, % of family total)
- Category breakdown table (name + amount + proportional bar)

---

### 8. Vertrag hinzufügen / Onboarding

**Route:** `/onboarding`  
**Back nav:** Yes — "Neuer Vertrag"

**3-step flow** (step indicator: numbered circles + connector lines):

**Step 1 – Daten:**
- Versicherer select: Merkur, UNIQA, Generali, Wiener Städtische, Allianz
- Polizzennummer text input (creditCard icon)
- "Weiter" button (disabled until both filled)

**Step 2 – Dokument:**
- Drop zone for PDF upload
- "Vertrag analysieren" button → 2.5s parsing animation (spinner + progress bar) → advance to step 3

**Step 3 – Bestätigen:**
- Green checkCircle icon (56×56, `#DCFCE7` bg)
- Extracted benefits list (name + period + limit amount)
- "Vertrag speichern" → navigate to Benefits

---

### 9. Einstellungen / Settings

**Route:** `/settings`

**Sections** (uppercase 12px letter-spaced section headers):

**Konto:** Profil | E-Mail | Sprache

**Versicherungsportal:** 
- Security vault banner: green shield icon, "Sicherer Tresor", "AES-256 verschlüsselt · Nur auf Ihrem Gerät"
- ÖGK-Portal (hinterlegt — green dot indicator)
- Merkur-Portal (hinterlegt — green dot indicator)

**Verträge:** Merkur Sonderklasse + policy number | Vertrag hinzufügen

**Sonstiges:** Abmelden (danger red, logout icon)

---

## Component Specifications

### Invoice Card

```
Height: auto (padding 14px)
Layout: flex row, gap 12px
Left:   Avatar (38×38, member color, radius 19, initials)
Center: Provider name (14px bold, truncated) 
        Patient · Date (11px tertiary, row below)
        Status pill + relative time
Right:  Amount (15px bold, tabular-nums)
Hover:  translateY(-1px), shadow-md
```

### Status Pill

```
Padding:      3px 8px (sm) | 4px 10px (md)
Radius:       9999px
Font:         11–12px, weight 600, letter-spacing 0.01em
Colors:       see status table above
```

### Family Filter Pills

Horizontal scroll row, `padding: 0 20px`, gap 8px, no scrollbar.  
Each pill: `padding: 6px 12px`, radius pill.  
Active: member color background (or accent for "Alle"), white text.  
Inactive: surfaceAlt background, secondary text.  
Member pills include a 20×20 avatar circle (initials, 9px bold) at left.

### Avatar

```
Size:       configurable (default 36px), circular (radius 50%)
Background: memberColor + '18' (10% opacity)
Text:       memberColor, initials, weight 700, ~33% of size
```

### Drop Zone

```
Padding:    40px
Border:     2px dashed, border color on drag-over = accent
Background: surfaceAlt (drag-over: accentLight #F0FDFA)
Radius:     16px
Center:     56×56 icon container (accentMid bg, radius 16) + camera icon (28px teal)
            "Foto aufnehmen oder Datei wählen" (15px bold)
            "Beleg fotografieren oder PDF hochladen" (13px secondary)
Input:      hidden file input, accept="image/*,.pdf", capture="environment"
```

### Vertical Pipeline Stepper

Each row = horizontal flex (gap 14px):
- **Left column** (width 28px): circle dot (28×28, radius 14) + vertical line connector
  - Complete: filled with status color, white checkmark
  - Active: status bg fill, status color border (2px), outer ring `${statusColor}22` (4px box-shadow)
  - Upcoming: surfaceAlt fill, tertiary number
- **Right column**: label (14px, weight: 600 active / 500 complete / 400 upcoming), timestamp (12px tertiary), "Aktiv" pulse badge (if active)

Connector line: width 2px, flex: 1, color = status color (complete) or border color (upcoming).

### Progress Bar

```
Track:  height 6–8px, radius = height, background surfaceAlt
Fill:   same radius, color based on % (green/amber/red)
Label:  flex space-between below bar, 12px weight 500
        Left: "€ X übrig" in fill color
        Right: "€ used / € limit" in tertiary
```

### Primary Button

```
Height:         44px (md) | 52px (lg) | 36px (sm)
Padding:        0 20px
Background:     #0D9488 (accent)
Color:          #FFFFFF
Border-radius:  12px
Font:           14–16px, weight 600
Hover:          #0F766E
Active:         scale(0.97)
Disabled:       opacity 0.5
Loading:        spinner icon replaces left icon, pulsing
Full-width:     width: 100%
```

### Input Field

```
Height:     48px
Padding:    0 14px
Background: surfaceAlt
Border:     1.5px solid transparent (focus: accent, error: #DC2626)
Radius:     12px
Font:       15px
Label:      13px weight 600, secondary color, 6px margin-bottom
```

### KCCard

```
Background: surface (#FFFFFF)
Border:     1px solid border (#E5E3DE)
Radius:     16px
Shadow:     shadow-card
Hover:      shadow-md + translateY(-1px)
```

---

## Navigation & Routing

```
/              → Home (Übersicht)
/invoices      → Belege list
/invoices/:id  → Beleg-Detail (back nav)
/upload        → Upload (back nav, no bottom nav)
/benefits      → Leistungen
/stats         → Statistiken
/onboarding    → Vertrag hinzufügen (back nav, no bottom nav)
/settings      → Einstellungen
/login         → Login (no top bar, no bottom nav)
```

**Screens WITHOUT bottom nav:** upload, detail, onboarding  
**Screens WITH back arrow instead of logo:** upload, detail, onboarding

Page transition: `opacity 0→1 + translateY(6px→0)`, duration 350ms ease.

---

## State Management

### Global state needed:
- `loggedIn: boolean`
- `activeMember: 'all' | 'maria' | 'thomas' | 'luisa' | 'felix'` — shared across all tabs
- `selectedInvoice: Invoice | null`
- `darkMode: boolean`

### Family member filter:
`activeMember` persists across tab changes. Filters: invoices, benefits, stats, dashboard figures.

### Invoice filtering (Belege screen):
- `search: string` — matches `provider` (case-insensitive)
- `filter: 'all' | 'in_progress' | 'abgeschlossen'`
  - `in_progress`: status ≠ `abgeschlossen`
  - `abgeschlossen`: status === `abgeschlossen`

### Upload flow:
- `file: File | null`
- `preview: string | null` (data URL for images)
- `uploading: boolean` → 2s simulated delay → `success: boolean` → navigate

### Stats view tabs:
- `view: 'monthly' | 'yearly' | 'members'`

---

## Data Models

### Invoice

```ts
interface Invoice {
  id: number;
  provider: string;          // e.g. "Apotheke Zur Gesundheit"
  amount: number;            // EUR float
  date: string;              // "DD.MM.YYYY"
  uploaded: string;          // "DD.MM.YYYY"
  relativeTime: string;      // "heute" | "vor 2 Tagen" | "vor 3 Wochen"
  status: StatusKey;
  patient: string;           // full name
  memberId: 'maria' | 'thomas' | 'luisa' | 'felix';
  category: string;          // e.g. "Physiotherapie"
  contract: string;          // e.g. "Merkur Sonderklasse"
  pipeline: 'standard' | 'pharmacy';
  currentStep: number;       // 0-indexed step in pipeline array
}
```

### BenefitContract

```ts
interface BenefitContract {
  contract: string;          // e.g. "Merkur Sonderklasse"
  policyNumber: string;      // e.g. "MS-2024-78912"
  members: MemberBenefits[];
}

interface MemberBenefits {
  memberId: string;
  name: string;
  benefits: Benefit[];
}

interface Benefit {
  name: string;              // e.g. "Physiotherapie"
  used: number;              // EUR used this period
  limit: number;             // EUR limit for period
  period: 'jährlich' | '2-jährlich' | 'halbjährlich';
}
```

### Monthly Stats

```ts
interface MonthlyStats {
  month: string;             // "Jan" | "Feb" | ...
  total: number;
  members: Record<MemberId, number>;
}
```

---

## Animations & Transitions

| Name          | Trigger                          | Spec |
|---------------|----------------------------------|------|
| Page enter    | Screen mount                     | opacity 0→1 + translateY 6px→0, 350ms ease |
| Count-up      | Hero amount on dashboard mount   | easeOut cubic, 1200ms |
| Button press  | mousedown                        | scale(0.97), 150ms |
| Stepper       | Active step dot                  | box-shadow pulse, CSS animation |
| Pulse badge   | Active status dot in stepper     | opacity 1→0.4→1, 1.5s infinite |
| Upload success| checkCircle icon appear          | scale 0.5→1.1→1 (`kcPop`), 400ms |
| Bar chart     | Width on mount                   | width 0→final, 500ms ease |
| Progress bar  | Width on mount                   | width 0→final, 600ms ease |
| Spinner       | Loading states                   | 360deg rotation, 800ms linear infinite |
| Parse progress| Onboarding step 2                | width 0→100%, 2.5s ease forwards |

---

## Icons

All icons are 24×24 stroke-based SVG (strokeWidth 1.8, strokeLinecap round, strokeLinejoin round). Uses the following names (map to your icon library):

`home`, `receipt`, `barChart`, `trending`, `plus`, `settings`, `camera`, `upload`, `x`, `check`, `checkCircle`, `chevronRight`, `chevronDown`, `arrowLeft`, `search`, `clock`, `send`, `scan`, `inbox`, `shield`, `lock`, `user`, `globe`, `logout`, `eye`, `eyeOff`, `file`, `alertCircle`, `mail`, `loader`, `creditCard`, `edit`, `filter`, `bell`

---

## Responsive Behaviour

- **≤430px (mobile):** Full-width, no border-radius on app shell, native scroll
- **>430px (desktop/tablet):** App shell max-width 430px, centered, border-radius 24px, height min(100vh - 40px, 900px), `#E8E7E4` page background

No other responsive breakpoints — this is a mobile-first app that happens to work on desktop.

---

## Accessibility

- All interactive elements reachable by keyboard
- Focus ring: `2px solid #0D9488`, offset 2px
- Buttons have `cursor: pointer`; disabled buttons `cursor: not-allowed`, `opacity: 0.5`
- Color is not the only status indicator (text labels always present alongside color)
- All amounts use `font-variant-numeric: tabular-nums`

---

## Files in this Package

| File | Contents |
|------|----------|
| `KaiserClaim.html` | Entry point — loads all scripts, global CSS, font imports |
| `kc-system.jsx` | Design tokens (`KC`), all shared components (icons, cards, buttons, inputs, stepper, etc.) |
| `kc-screens-main.jsx` | Login, Home/Dashboard, Upload screens |
| `kc-screens-detail.jsx` | Invoice List, Invoice Detail, Benefits, Onboarding, Settings |
| `kc-screens-stats.jsx` | Statistics screen (monthly/yearly/members views) |
| `kc-app.jsx` | App shell, router, mock data, Tweaks panel |
