# ADR-039: Mobile-Friendly Native Notification Replacement

## Status
Accepted

## Date
2026-05-20

## Context
Previously, ReadOmni AI relied exclusively on native JavaScript `alert()` and `confirm()` dialogs to handle user feedback and destructive actions (like deleting books or overwriting titles). While functional, native dialogs present several critical issues:
1. **Poor Mobile Experience:** Native dialogs cannot be styled, look jarring on iOS/Android, and can sometimes block the entire screen unpredictably.
2. **Interruptive Flow:** They halt main thread execution, which disrupts the sleek glassmorphic UX of the application.
3. **PWA Limitations:** Modern Progressive Web Apps (PWAs) are discouraged from using native modals because they break the native-app illusion.

We need a modern, React-native notification system that provides toasts for passive feedback and styled modal dialogs for active confirmations, without introducing massive global state management overhead.

## Decision
1. **Toasts (`sonner`):** We have integrated `sonner` for all non-blocking notifications. It is lightweight, supports rich colors, stacks beautifully on mobile, and works effortlessly outside of complex React contexts. All previous `alert()` calls have been replaced with `toast.success()`, `toast.error()`, or `toast.info()`.
2. **Confirmations (Radix UI `AlertDialog`):** For destructive actions, we have created a custom `AlertDialog` component built on `@radix-ui/react-alert-dialog`.
3. **Imperative Confirm Hook:** To retain the ease of use of the native `confirm()` API without rewriting complex local component state everywhere, we implemented a global `ConfirmProvider` and `useConfirm()` hook. 
   - Usage: `const isConfirmed = await confirm({ title: "Delete?", ... })`
   - This pattern isolates the modal state to a single top-level provider in `App.tsx` while allowing any component to safely pause execution and wait for a user's choice.

## Alternatives Considered
- **MUI Dialogs / Snackbar:** We already have `@mui/material` installed. However, MUI's Snackbar requires extensive boilerplate to trigger from anywhere in the app without Redux/Context overhead. `sonner` is much more ergonomic. For dialogs, Radix primitives are easier to style with our custom Tailwind v4 glassmorphic theme than overriding MUI's emotion-based themes.
- **Zustand Global State:** Considered using a Zustand store to handle generic dialogs. Decided against it because a Context Provider (`ConfirmProvider`) is sufficient for this single use-case and keeps the dependency graph small.

## Consequences
- **UX Improved:** Notifications are now non-blocking and blend perfectly with the app's visual identity.
- **Mobile Friendly:** Toasts appear at the bottom on mobile screens, making them easily readable without blocking core UI elements.
- **DX Maintained:** Developers can still write sequential async logic using the `useConfirm` hook without splitting functions or managing `isOpen` state locally in every component.
