# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The demo is shown inside the team, as material for brainstorming (confirmed by the owner, 2026-11-24). It is not yet in front of customers, judges or real members.

The roles the demo plays out are:

- **Member** (household or company): photographs recyclables on a phone, books a pickup, shows a QR at the door.
- **Driver**: follows the day's route on a phone, scans the QR, weighs each bag.
- **Admin**: runs the back office on a wide screen: dispatch, acceptance rules, prices, partners, carbon.
- **Partner** (factory or scrap shop): sets today's buying price and acknowledges notices.

## Product Purpose

Door-to-door pickup of sorted recyclables in Bangkok. A member's photo becomes a pickup request (AI counts bags, sorts materials, counts pieces); the system routes trucks; the driver verifies by QR and weighs; the load goes to a sorting centre and on to factories. For company members, weighed kilograms become carbon figures and can be filed into the GrowGreen carbon-accounting platform as draft activity data.

## Positioning

Every number downstream comes from a weighed, QR-verified pickup, not from an estimate the member typed in.

## Operating Context

- Members and drivers use a phone, outdoors or at a doorway. Admin uses a desktop.
- The app is a PWA served by one FastAPI process; front end is plain HTML, CSS and JavaScript with no build step.
- Maps are Leaflet with OpenStreetMap tiles.

## Capabilities and Constraints

- All interface text is Thai.
- AI is used in two places only: reading the photo, and turning a dispatcher's spoken-style command into an action. A visible badge says when AI results are simulated.
- Two carbon figures are always shown separately and never netted: avoided emissions, and recycling process emissions (Scope 3 category 5).
- All data, prices, names and contacts in the demo are synthetic and labelled as such. One exception: when the GrowGreen connector is linked with a real API key, the carbon page shows that key's real organisation name, site code, key prefix and draft document numbers.
- Undecided: who the first external audience will be.

## Brand Commitments

- Name: แยกถูก รับถึงบ้าน.
- Green identity and the existing logo mark stay.
- The admin back office is dark; member, driver and partner views are light.
- Thai-only wording.

## Evidence on Hand

- Seeded demo data (`app/seed.py`), price references with sources (`app/config.py`), emission factors with sources.
- No customers, testimonials, photography or real operating data exist. None may be invented.

## Product Principles

1. The weighed number is the product; show where each figure came from.
2. Say plainly when something is simulated or estimated.
3. A member should finish a pickup request one-handed.
4. It should read as a Thai product, not a translated template.

## Accessibility & Inclusion

No formal standard has been set. Members include older household users on small phones.
