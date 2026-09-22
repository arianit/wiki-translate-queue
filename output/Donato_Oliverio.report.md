# Report: Donato Oliverio

- **Source:** `it.wikipedia.org/wiki/Donato_Oliverio`, revid `152281725` (2026-09-01T08:26:46Z)
- **Target:** `sq.wikipedia.org/wiki/Donato Oliverio` — new page (no existing sqwiki article; Wikidata Q1240717 has no `sqwiki` sitelink)
- **Model / provider:** `deepseek-v4.1-flash` / `opencode-go` (manual translation, no harness LLM subprocess)
- **Skills:** itwiki-sqwiki-translation (+ wikiterms, wikiqa)

## Link targets

Native sqwiki targets used (verified directly via `action=query`):

| Source (itwiki) | sqwiki target |
|---|---|
| Eparchia di Lungro | `Eparhia e Ungrës` (h-spelling; `Eparkia e Ungrës` is a redirect) |
| Arbëreshë | `Arbëreshët në Itali` |
| Chiesa cattolica italo-albanese | `Kisha Bizantine Italo-Arbëreshe` |
| Eparchia di Piana degli Albanesi | `Eparkia e Horës së Arbëreshëvet` |
| Rito bizantino | `Liturgjia bizantine` |
| Cattedrale di San Nicola di Mira | `Kryekisha e Shën Kollit` |
| San Nicola di Mira | `Nikolla i Mirës` |
| Lungro | `Ungra` |
| Cosenza | `Kozenca` |
| San Benedetto Ullano | `Shën Benedhiti` |
| San Basile | `Shën Vasili` |
| Grottaferrata | `Grottaferrata` |
| Italia meridionale | `Italia jugore` |
| Lingua albanese / italiana / francese / greca | `Gjuha shqipe` / `Gjuha italiane` / `Gjuha frënge` / `Gjuha greke` |
| filosofia / teologia | `Filozofia` / `Teologjia` |
| Seminario | `Seminari` |
| Compagnia di Gesù | `Jezuitët` |
| Slovacchia | `Sllovakia` |
| Ordine di Skanderbeg | `Urdhri i Skënderbeut` |
| Papa Benedetto XVI | `Papa Benedikt XVI` |
| Papa Benedetto XV | `Papa Benedikti XV` |
| Ilir Meta | `Ilir Meta` |
| Arberia | `Arbëria` |
| Giorgio Demetrio Gallaro / Raffaele De Angelis | native articles exist |

`{{ill}}` used (no sqwiki target): `Abbazia territoriale di Santa Maria di Grottaferrata`, `Giovanni Crisostomo`.

Left unlinked (no sqwiki target, kept as plain text): the episcopal-genealogy names (Cirillo VI Serpetzoglou, Agatangelo I, Gioacchino II Kokkades, Antim I Chalakov, Nilo Isvoroff, Michel Petkoff, Michel Miroff, Isaias Papadopoulos, Giovanni Mele), Giovanni Stamati, Ercole Lupinacci, Salvatore Nunnari, Cyril Vasiľ, Kongregata për Kishat Orientale, kuria dioqezane, Leksionari Apostolos, Institutin Pontifikal Oriental, Universiteti Pontifikal "Shën Thoma i Akuinit", Marri, arkidioqezën e Kozencës-Bisignano.

## Templates

- `{{Vescovo}}` → **`{{Infobox Christian leader}}`** (confirmed present; all params checked against the live template's param list — no "unknown parameter" maintenance category was triggered).
- `{{Bio}}` → **merged into the same infobox and dropped** as redundant: sqwiki's `{{Infobox Christian leader}}` already carries birth date/place, nationality and occupation, which are the only fields the itwiki `{{Bio}}` added. Two stacked infoboxes are not the sqwiki convention (cf. `Joan Pelushi`).
- `{{Cita web}}` → `{{Cite web}}` (English params; `it`/`sq` language codes added).
- `{{interprogetto}}` → `{{Sisterlinks}}`.
- `{{Controllo di autorità}}` → `{{Authority control}}`.
- `{{Onorificenze}}` → **dropped**, rendered as a `== Nderime ==` prose bullet (no sqwiki equivalent).
- `{{Box successione}}` → **dropped**; the predecessor/successor facts moved into the infobox `predecessor`/`successor` fields.
- `{{Collegamenti esterni}}` → **dropped** (no sqwiki equivalent); the Jemi.it card kept as a manual `{{Cite web}}` bullet and the Vatican Insider / photo links as plain external links.
- `{{Portale}}`, `{{Calcola età}}` → dropped (no sqwiki equivalent / not present).

## Citations

Language codes: `it` ×2, `sq` ×1. All dates ISO (`2014-12-12`, `2014-12-17`, `2015-07-14`, `2025-12-23`). Institution names unlinked inside refs.

## Choices to review

- **Source date discrepancy preserved:** the itwiki body says the Skanderbeg honour was conferred on **6 November 2018**, while the itwiki `{{Onorificenze}}` box says **5 November 2018**. Both were kept as-is; the discrepancy is not resolved in the source.
- Archives kept (not stripped) on both `Cite web` citations.
- The `== Altri progetti ==` heading was dropped; its `{{interprogetto}}` became a bare `{{Sisterlinks}}` box near the external links.
- Categories chosen from existing sqwiki usage: `Arbëreshë në Itali`, `Italianë me prejardhje arbëreshe`, `Peshkopë katolikë shqiptarë`, `Kisha katolike italo-shqiptare`, `Udhëheqës fetarë të krishterë`, `Lindje 1956`, `Njerëz që jetojnë`.

## Verification performed

- `action=parse` render of the draft on sqwiki: no script/Cite errors, no maintenance categories, all templates resolved.
- All link targets checked against the live sqwiki API before drafting.
- Images (`Eparca Donato Oliverio center.jpg`, `Template-Bishop (eastern rites).png`) confirmed present on Commons.

## Attribution

`{{Përkthyer nga|it|Donato Oliverio|1 shtator 2026|152281725}}` on the Talk page; edit summary `Përkthyer nga italishtja, sipas artikullit it:Donato Oliverio, versioni i datës 1 shtator 2026 (revizioni 152281725)`.
