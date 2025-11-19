# Notification System

## Overview
The notification system enables users to share resources and blueprints with other users through a secure copy-on-share mechanism.

## Features

### 🔔 Notification Indicator
- Red dot appears on the bell icon when there are pending notifications
- Shows count in tooltip when hovering over the icon

### 📋 Notification List
- **Received Notifications**: Shows all notifications sent to the current user
- **Sent Notifications**: Shows all notifications sent by the current user
- **Status Indicators**: Visual badges showing the status of each notification
  - 🟡 Pending - Awaiting response
  - 🟢 Accepted - Share was accepted
  - 🔴 Declined - Share was declined
  - ⚫ Canceled - Share was canceled

### ✅ Action Buttons
For received notifications with "pending" status:
- **Accept Button (✓)**: Accept the shared item (triggers API `/share.accept`)
- **Decline Button (✗)**: Decline the shared item (triggers API `/share.decline`)

### 📤 Send Notification
Send a new notification with:
- **Recipient User ID**: Username of the person to share with
- **Item Type**: Dropdown selection between "Resource" or "Blueprint"
- **Item ID**: Unique identifier of the item to share
- **Message**: Optional message to include with the share

## Usage

1. **Viewing Notifications**: Click the bell icon in the header
2. **Accepting Shares**: Click the green checkmark on pending received notifications
3. **Declining Shares**: Click the red X on pending received notifications
4. **Sending Shares**: Use the "Send Notification" tab to create new shares

## Technical Details

### API Endpoints Used
- `POST /shares/share.create` - Create new share invitation
- `GET /shares/shares.list` - List share invitations
- `POST /shares/share.accept` - Accept share invitation
- `POST /shares/share.decline` - Decline share invitation

### Auto-refresh
- Notifications are automatically refreshed every 30 seconds
- Notifications are immediately refreshed when user logs in
- Local state updates immediately when accepting/declining

### Error Handling
- All API errors are displayed in the modal
- Failed operations can be retried
- Offline status is handled gracefully

## Components

- `NotificationPanel`: Main dropdown panel component with tabs
- `NotificationContext`: React context for state management
- `Header`: Updated to include notification indicator and modal trigger
- API service functions in `api/shares.ts`
