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
| `BASE_URL` | `https://getnovena.app/` | Set by the cutover PR, together with `CNAME`. Before it, the site was built for `https://kipster254.github.io/novena-site/` |
| `PLAY_LIVE` | `1` | The Play listing is public (since 2026-09-28): shows the badge and UTM link. `0` restores "coming soon" |
| `LANGS` | `en,es,pt-BR` | A language is normally added on its own branch and merged after a native reader signs it off. **es and pt-BR went live 2026-09-28 under an owner waiver of that gate** (novena `docs/execution/decision-log.md`); their native read is still owed |

`check.py` fails if `privacy.html` differs from the app repo's copy, if any page
loads anything from another host, if any paid novena's text appears anywhere,
if a free novena's text or source line doesn't match the catalog, or if any
link is broken.

Fonts: Instrument Serif, Newsreader and Sora, SIL Open Font License 1.1
(`assets/fonts/OFL-*.txt`), files from `@fontsource/*@5.3.0`.
