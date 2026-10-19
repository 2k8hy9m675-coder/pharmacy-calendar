# Personal UKIM Pharmacy Calendar

Personal Apple Calendar feed generated from the public timetable used by:
https://srgjanc.github.io/schedule/index_supabase.html

## Filters

Programme: Магистер по фармација 2021

- Фармакогнозија — group 3
- Фармацевтска технологија – напредно ниво — group 4
- Биофармација — group 3
- Храна и исхрана — group 1

Фармацевтска хемија 3 is not included.

## Setup

1. Create a PUBLIC GitHub repository named `pharmacy-calendar`.
2. Upload all files from this folder, including the `.github` folder.
3. Open Actions → "Update calendar" → Run workflow.
4. Open Settings → Pages.
5. Under "Build and deployment", choose "Deploy from a branch".
6. Select `main` and `/ (root)`, then Save.
7. Once Pages is live, the subscription URL should be:

   https://2k8hy9m675-coder.github.io/pharmacy-calendar/schedule.ics

8. On iPhone/iPad:
   Calendar → Calendars → Add Calendar → Add Subscription Calendar.
   Paste the URL above.

On Mac:
   Calendar → File → New Calendar Subscription, then paste the URL.

## Notes

- GitHub Actions regenerates the feed hourly.
- Apple Calendar controls when it refreshes subscribed calendars, so changes may not appear instantly.
- Events currently default to 2 hours because the source timetable exposes a start time but no end-time field.
