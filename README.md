# WBN Instagram autopost

Post automatisch de grootste headlines van worldbaseballnews.org op Instagram: eigen visual (artikelfoto + titel in WBN-huisstijl), caption met "link in bio" en league-hashtags. Volledig gratis: GitHub Actions + de officiële Instagram API.

## Hoe het werkt

Elke 3 uur (01, 04, 07, 10, 13, 16, 19 en 22 uur NL-tijd) leest de bot de RSS-feed van de site (alle artikelen van de afgelopen 20 uur, niet alleen de hero) en geeft elk artikel een **nieuwswaarde-score van 0–100**:

| Onderdeel | Punten |
|---|---|
| League | elke league start gelijk: +20 |
| Onderwerp (sterkste telt, elk extra onderwerp +5) | titel gewonnen +45 · grote prijs (MVP, Cy Young, Sawamura) +38 · historisch (no-hitter, record) +35 · transfer/contract/ontslag +28 · finale-serie +32 · playoffs +24 · topprestatie (walk-off, grand slam, shutout) +12 · gewone wedstrijd +6 |
| Aftrek | jeugd/U-18 −18 · bestuurlijk/staf/schema/regen −12 · preview −6 · ouderdom −0,6 per uur |
| Lezers | staat in "Most read" op de homepage +10 |
| Variatie | zelfde verhaal als eerdere post vandaag −35 · elke eerdere post uit dezelfde league vandaag −12 · elke post uit die league eerder deze week −3 (zo komen leagues om de beurt) |
| Toeval | +0 tot 8 willekeurig, vast per artikel per dag, zodat gelijkwaardige artikelen eerlijk om de beurt winnen |

**Wanneer gaat er iets live?**
- **Score ≥ 60**: bij de eerstvolgende run (topnieuws).
- **Score 40–59**: wacht tot het avondvenster (18:30–23:30 NL), en daar gaat het beste resterende artikel uit als er nog ruimte is.
- **Onder 40**: wordt niet gepost.
- Max 3 posts per dag, max 1 per run. De **derde post blijft tot 15:00 vrij**, behalve voor breaking news (≥ 80), zodat er altijd ruimte is voor groot nieuws later op de dag.

Elke run zet de volledige ranking met uitleg in de samenvatting van de GitHub Action, zodat je precies ziet waarom iets wel of niet gekozen is. Lokaal: `python bot.py rank`. Alle punten, woorden en tijden staan in `config.json` en zijn aan te passen.

**Visual & caption**: 1080×1350 met artikelfoto, kop (ingekort naar de SEO-titel of een zinsdeel als hij langer is dan 70 tekens), league-label en datum. De caption bevat een onderwerp-emoji, de kop, de meta description, "link in bio" en league-hashtags.

## Eenmalige setup (± 20 minuten)

### 1. Instagram omzetten naar professioneel account
Instagram-app → Instellingen → *Accounttype en tools* → *Overstappen naar professioneel account* → kies **Bedrijf** (categorie bijv. *Media/nieuwsbedrijf*). Een Facebook-pagina koppelen is **niet** nodig.

### 2. Meta-app maken en token ophalen
1. Ga naar [developers.facebook.com](https://developers.facebook.com) → *My Apps* → *Create app*.
2. Kies de use case voor het beheren van content op Instagram (Instagram API met Instagram-login) en maak de app aan.
3. Open in de app *Instagram* → *API setup with Instagram login* → bij **Generate access tokens**: *Add account*, log in met het WBN Instagram-account en klik op *Generate token*.
4. Kopieer de **token** en het **Instagram user ID** dat daar staat.

De app mag in Development-modus blijven: je post alleen naar je eigen account, daar is geen App Review voor nodig.

### 3. GitHub-repo
1. Maak een **publieke** repo `finnkops-code/wbn-instagram` en zet deze bestanden erin. Publiek is nodig omdat Instagram de visual zelf ophaalt via een openbare URL; je tokens staan veilig in Secrets en zijn nooit zichtbaar. Bijkomend voordeel: Actions-minuten zijn onbeperkt gratis voor publieke repo's.
2. *Settings → Secrets and variables → Actions → New repository secret*:
   - `IG_ACCESS_TOKEN` — de token uit stap 2
   - `IG_USER_ID` — het Instagram user ID (optioneel, de bot zoekt het anders zelf op)
   - `GH_PAT` — een [fine-grained token](https://github.com/settings/personal-access-tokens/new) met alleen toegang tot deze repo en permissie **Secrets: Read and write**. Hiermee ververst de bot elke maandag zelf de Instagram-token (die verloopt anders na 60 dagen).
3. *Settings → Actions → General → Workflow permissions* → **Read and write permissions**.

### 4. Testen en live zetten
1. Tab *Actions* → **Instagram autopost** → *Run workflow* met **dry_run aangevinkt**. Je ziet de caption in de samenvatting en de visual in de map `posts/`.
2. Goed? Nog een keer *Run workflow* zonder dry_run: de eerste echte post gaat live.
3. Zet in je Instagram-bio de link `https://worldbaseballnews.org`.

Wil je bij livegang niet de headlines van vandaag posten maar pas vanaf het eerstvolgende nieuwe artikel? Draai dan één keer lokaal `python bot.py seed` en commit `state/posted.json`.

## Handig om te weten

- **Lokaal previewen**: `pip install -r requirements.txt` en dan `python bot.py preview` (huidige headlines) of `python bot.py preview <artikel-url>`. Visuals + captions komen in `preview/`.
- **Timing**: GitHub draait geplande workflows soms 5–15 minuten later dan gepland. Topnieuws komt dus binnen ruim 3 uur na publicatie online.
- **Fout bij posten?** GitHub mailt je bij een mislukte run; de bot probeert het de volgende run gewoon opnieuw. Verlopen token → stap 2 opnieuw en `IG_ACCESS_TOKEN` vervangen.
- **Opruimen**: visuals ouder dan 14 dagen worden automatisch uit de repo verwijderd (Instagram bewaart z'n eigen kopie).
- **Fonts**: Oswald en Figtree (de fonts van de site, SIL Open Font License).

## Alternatieve koppeling via Facebook (legacy)

Werkt de pagina *API setup with Unified login* niet, dan kan de bot ook via de aan Instagram gekoppelde Facebook-pagina posten:
1. Koppel Instagram aan de WBN Facebook-pagina (Accountcentrum).
2. Haal een **page access token** op (Graph API Explorer → permissies `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management` → long-lived token → page token). Een page token van een long-lived user token verloopt niet.
3. Voeg in de Graph API Explorer ook `pages_manage_posts` toe als je dezelfde post op Facebook wilt (foto + caption met klikbare artikellink). Zonder die permissie post de bot alleen op Instagram.
4. Zet in GitHub: secret `IG_ACCESS_TOKEN` = page token, secret `IG_USER_ID` = Instagram business account-ID, en onder *Variables* `IG_API_ROUTE` = `facebook`. `GH_PAT` is dan niet nodig.
