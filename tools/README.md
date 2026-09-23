# Building getnovena.app

The site is plain HTML generated from the app's own content files. Nothing is
loaded from any other host, there is no JavaScript, and `privacy.html` is never
generated: it is the Play-held privacy policy, copied byte for byte from
`kipster254/novena`'s `site/privacy.html`.

```bash
git clone https://github.com/kipster254/novena ../novena   # read-only source
pip install qrcode                                          # parish-kit QR, generated offline
NOVENA_REPO=../novena python3 tools/build.py
NOVENA_REPO=../novena python3 tools/check.py                # must print OK before any merge
```

Switches (environment variables, or edit the defaults in `build.py`):

| Variable | Default | When it changes |
|---|---|---|
| `BASE_URL` | `https://kipster254.github.io/novena-site/` | The cutover PR sets `https://getnovena.app/` (and adds `CNAME`) |
| `PLAY_LIVE` | `0` | `1` once the app is public on Google Play: shows the badge and UTM link instead of "coming soon" |
| `LANGS` | `en` | A language is added only on its own branch, merged after a native reader signs it off |

`check.py` fails if `privacy.html` differs from the app repo's copy, if any page
loads anything from another host, if any paid novena's text appears anywhere,
if a free novena's text or source line doesn't match the catalog, or if any
link is broken.

Fonts: Instrument Serif, Newsreader and Sora, SIL Open Font License 1.1
(`assets/fonts/OFL-*.txt`), files from `@fontsource/*@5.3.0`.
