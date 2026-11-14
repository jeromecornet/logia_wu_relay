# Logia Weather Underground relay for Home Assistant

Sensors for a Logia weather station that insists on reporting to
`rtupdate.wunderground.com`.

The station POSTs every few seconds to Weather Underground. Instead of letting it
reach the internet, a DNS override points `rtupdate.wunderground.com` at a local
web server, which dumps the decoded query string into a small JSON file. This
integration turns that file into Home Assistant sensors — no cloud account, no
WU credentials.

## How the relay works

1. The router answers `rtupdate.wunderground.com` with the LAN address of a local
   web server (e.g. a Synology Web Station portal).
2. That server runs a tiny PHP endpoint (or anything else) which writes the
   incoming parameters to a JSON file, e.g.

   ```php
   <?php
   $path = '/volume1/web/weatherstation/history/weather.json';
   $params = $_GET;
   $params['dateutc'] = (new DateTime())->getTimestamp();
   // Write to a temp file and rename: readers must never see a truncated file.
   file_put_contents($path . '.tmp', json_encode($params));
   rename($path . '.tmp', $path);
   echo 'success';
   ```

3. This integration polls that JSON file and exposes the readings.

## Installation

Copy `custom_components/logia_wu_relay` into your Home Assistant `config`
directory, or add this repository as a custom repository in HACS.

## Configuration

### Through the UI (recommended)

**Settings → Devices & Services → Add integration → Logia Weather Underground
relay**, then enter:

| Field          | Required | Description                                  |
| -------------- | -------- | -------------------------------------------- |
| `Payload URL`  | yes      | URL of the JSON payload written by the relay  |
| `Device name`  | no       | Prefix for the entity names (default `Logia`) |

The URL is fetched once during setup, so the relay must be reachable when you
add it.

### Through YAML (legacy, migrated automatically)

```yaml
sensor:
  - platform: logia_wu_relay
    name: "Logia 5-1 PWS"
    url: "http://<web-server>/weatherstation/history/weather.json"
```

This is imported into a config entry on the first start: entities and history are
kept (unique IDs are unchanged), and the block then does nothing but log a
warning on every start — remove it once the entry exists.

## Entities

Per device, 14 entities are created: outdoor temperature, dew point, relative
humidity, atmospheric pressure, wind speed, wind gust, wind direction, hourly
and daily rain, indoor temperature and humidity, plus computed *Feels Like*,
*Humidex* and *Wind Chill* values (Environment Canada formulas).

Readings older than 15 minutes report as `unknown` so a silent station does not
keep showing a stale value.

## Notes

- Set up as a config entry (UI or YAML import), so the weather station device is
  attached to an integration entry instead of floating free — required since
  Home Assistant deprecated device-less YAML platforms.
- All entities share a single HTTP request per poll cycle (5 s cache) instead of
  fetching the payload once per entity.
- Network errors, truncated payloads and missing keys degrade to `unknown`
  rather than raising.
- Since Home Assistant 2026.11, `DeviceInfo` no longer accepts `name_by_user`;
  use `name` instead. This version is fixed for that.
