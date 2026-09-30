# ADR-0011: Not the default SMS app in v1; minSdk 31

**Status:** Accepted (2026-09-30)

## Context

Android delivers every incoming SMS to the default SMS app (`SMS_DELIVER`) and, as a
notification, to every app holding `RECEIVE_SMS` (`SMS_RECEIVED`). The default app also
skips the system's warning when an app sends more than 30 SMS a minute, and its messages do
not appear in another app's inbox. Becoming the default means implementing a full messaging
app: an inbox, MMS, a compose screen and a service for quick replies.

The only target device is a Galaxy S21 Ultra on Android 15.

## Decision

- The app holds `RECEIVE_SMS` and `SEND_SMS` and listens for `SMS_RECEIVED`. It is not the
  default SMS app.
- The app's minimum SDK is 31 (Android 12), so `SmsManager` comes from `getSystemService`
  with no deprecated branches.

## Why

- A messaging app is a large product that has nothing to do with browsing.
- The app sends one request per tap, far below the 30-a-minute prompt.

## What it costs

- The server's frames also appear in the phone's normal messaging app, as unreadable text
  from the server's number. The onboarding guide says to mute that conversation.
- Android 15 treats SMS permissions for sideloaded apps as a "restricted setting", so the
  first install needs one extra toggle in App info. The onboarding guide shows it.

## What would change our minds

The duplicated frames in the messaging app becoming a real problem in daily use. Then the app
takes the SMS role and ships a minimal inbox (Phase 9 in the build plan).
