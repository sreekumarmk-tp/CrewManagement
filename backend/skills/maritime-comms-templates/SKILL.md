---
name: maritime-comms-templates
description: >-
  Templates and style guide for maritime crew sign-on/sign-off notifications.
  Use whenever drafting an email/notification to the Captain, Shore Manager, a
  departing crew member, or a joining crew member. Provides the required subject
  line format, mandatory fields, tone, and a ready template per recipient.
---

# Maritime Comms Templates / Style Guide

Apply this guide when composing any sign-on / sign-off notification before sending
it (e.g. via the `sendMail` tool). Pick the template that matches the recipient,
fill every mandatory field, and follow the tone and subject conventions below.

## Tone

- Professional, concise, and operational — this is fleet operations correspondence.
- Lead with the action/decision, then the supporting detail.
- Use the recipient's role title (Captain, Shore Manager) or full name for crew.
- No emojis. No marketing language. UTC for all times; ISO-8601 (YYYY-MM-DD) for dates.
- Keep the body under ~150 words unless attaching a document summary.

## Subject line convention

Format: `[<TYPE>] <Vessel> — <Subject> (<Crew/Ref>)`

- `<TYPE>` is one of: `SIGN-OFF`, `SIGN-ON`, `TRAVEL`, `COMPLIANCE`, `CREW-CHANGE`.
- Examples:
  - `[SIGN-OFF] MV Pacific Star — Replacement requested (Miguel Torres / Chief Officer)`
  - `[COMPLIANCE] MV Pacific Star — Sign-on cleared (Ivan Kovalenko)`

## Mandatory fields (every notification)

1. Vessel name
2. Crew member name + rank
3. Action / decision (what happened or what is required)
4. Reference or date (sign-off date, workflow ref, etc.)
5. Next step or required action from the recipient (or "No action required")

## Recipient templates

### 1. Captain

> Subject: `[SIGN-OFF] <Vessel> — Replacement requested (<DepartingCrew> / <Rank>)`
>
> Captain,
>
> Sign-off has been initiated for <DepartingCrew> (<Rank>) aboard <Vessel> at
> <Port>, effective <SignOffDate>. A replacement, <Replacement> (<Rank>,
> <MatchConfidence>% match), has been identified and is undergoing compliance
> validation. Travel for the departing crew is being arranged (ref <BookingRef>).
>
> Next step: <e.g. "Awaiting compliance clearance — you will be notified of the
> final sign-on decision.">
>
> — Fleet Operations

### 2. Shore Manager

> Subject: `[CREW-CHANGE] <Vessel> — Operational update (<DepartingCrew> → <Replacement>)`
>
> <ShoreManagerName>,
>
> Operational update for <Vessel>: <DepartingCrew> (<Rank>) is signing off at
> <Port> on <SignOffDate>. Proposed replacement: <Replacement> (<Rank>).
> Compliance status: <passed / warning / pending>. Travel package: <BookingRef>,
> port clearance <ClearanceId>.
>
> Next step: <e.g. "No action required — informational." or "Please confirm berth
> logistics for the joining crew.">
>
> — Fleet Operations

### 3. Departing crew member

> Subject: `[TRAVEL] <Vessel> — Your sign-off & travel details (<Crew>)`
>
> Dear <Crew>,
>
> Thank you for your service aboard <Vessel>. Your sign-off at <Port> is confirmed
> for <SignOffDate>. Travel home: <Airline> <FlightNumber>, departing <Port> on
> <DepartureDate> at <DepartureTime> UTC (booking <BookingRef>). Port clearance
> <ClearanceId> is approved.
>
> Next step: Please confirm receipt and carry your travel documents and port
> clearance to disembarkation.
>
> Safe travels,
> Fleet Operations

### 4. Joining crew member

> Subject: `[SIGN-ON] <Vessel> — Joining instructions (<Crew>)`
>
> Dear <Crew>,
>
> You have been selected to join <Vessel> as <Rank> at <Port>. Your documents have
> cleared compliance (<ComplianceStatus>, <Score>%). <If warnings: "Note the
> following conditions to resolve before sailing: <Warnings>.">
>
> Next step: Report to <Port> on <JoiningDate>; bring passport, medical
> certificate, STCW certificates, and visa.
>
> Welcome aboard,
> Fleet Operations

## Compliance-outcome phrasing

- **passed** → "cleared compliance" / "APPROVE sign-on".
- **warning** → "conditionally cleared" — list each warning and the remediation.
- **failed** → "did not clear compliance" — state the blocking failure(s) plainly;
  do not soften. The crew member is NOT signed on.
