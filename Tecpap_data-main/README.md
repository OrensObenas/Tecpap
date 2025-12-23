# TECPAP Scheduler - Frontend Dashboard

A real-time production simulation control dashboard built with React, TypeScript, and Vite. This application provides a complete interface to monitor and control a compressed production simulation via the TECPAP Scheduler FastAPI backend.

## Features

### Dashboard Live
- **Simulation Control**: Start and stop compressed time simulations with configurable parameters
- **Real-time State Monitoring**: Live polling of machine status, current job, queue size, and KPIs
- **Quick Actions**: One-click buttons to inject events (breakdowns, speed changes, shift controls)
- **Mini Event Log**: Recent events displayed in real-time

### Events & Logs
- **Manual Event Injection**: Send events with timestamps or "now"
- **Comprehensive Event Log**: Full history with filtering capabilities
- **Advanced Filters**: Filter by status (ignored), replanned events, or breakdown events
- **Search**: Text search across event types, values, and reasons

### Reports
- **Hourly Snapshots**: Complete view of production metrics hour by hour
- **Visual Charts**: Line graphs for downtime, producing time, completed jobs, and lateness
- **Auto-refresh**: Automatic polling when simulation is running

### Planning
- **Planning Preview**: View the current production schedule
- **Configurable Limit**: Display 30, 50, 100, or 200 jobs
- **CSV Export**: Download the complete planning as CSV

## Prerequisites

- Node.js 18+ and npm
- TECPAP Scheduler FastAPI backend running (default: http://127.0.0.1:8000)

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
npm install
```

3. Configure the API endpoint (optional):
```bash
cp .env.example .env
```

Edit `.env` to set your backend URL:
```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

If not configured, the app defaults to `http://127.0.0.1:8000`.

## Running the Application

### Development Mode

```bash
npm run dev
```

The application will start on `http://localhost:5173` (or another port if 5173 is busy).

### Production Build

```bash
npm run build
npm run preview
```

## Usage Guide

### Starting a Simulation

1. Navigate to **Dashboard Live**
2. Configure simulation parameters:
   - **Day Start**: Beginning of the simulated production day (e.g., 2025-01-15 08:00)
   - **Day End**: End of the simulated production day (e.g., 2025-01-15 16:00)
   - **Compress to (seconds)**: Real-world duration of the compressed simulation (default: 120s = 2 minutes)
   - **Tick (seconds)**: Polling interval for the simulation engine (default: 0.2s)
3. Click **Start**

The simulation will begin, and the dashboard will update in real-time showing:
- Simulated time (compressed)
- Machine status (running, down, speed)
- Current job details
- Queue size and remaining jobs
- KPIs (downtime, producing, idle, stopped, completed count)

### Injecting Events During Simulation

Use **Quick Actions** on the Dashboard:
- **Breakdown Start**: Simulate a major breakdown
- **Breakdown End**: End the current breakdown
- **Speed 0.8x / 1.0x / 1.2x**: Change machine speed
- **Shift Stop / Start**: Control shift status

Or use the **Events & Logs** page for more control:
- Select event type
- Enter value (e.g., "MAJOR", "1.2", "OF_12345")
- Choose "Send NOW" or "Send with timestamp"
- Submit

### Monitoring and Analysis

- **Dashboard Live**: Real-time view of current state
- **Events & Logs**: Detailed event history with filters
- **Reports**: Hourly reports with visual charts to analyze production efficiency
- **Planning**: View and export the current production schedule

## API Endpoints Used

The frontend consumes the following FastAPI endpoints:

- `GET /state` - Engine state (fallback)
- `POST /realtime/start` - Start compressed simulation
- `POST /realtime/stop` - Stop simulation
- `GET /realtime/state` - Real-time runner and engine state
- `GET /realtime/hourly` - Hourly reports
- `POST /events` - Send event with timestamp
- `POST /events/now` - Send event at current simulated time
- `GET /events/log?limit=N` - Event log history
- `GET /plan?limit=N` - Planning preview
- `GET /plan/export.csv` - Download planning as CSV

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── Badge.tsx
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── ErrorMessage.tsx
│   ├── LoadingSpinner.tsx
│   ├── SimpleLineChart.tsx
│   └── Toast.tsx
├── hooks/               # Custom React hooks
│   └── usePolling.ts    # Polling hook for real-time updates
├── pages/               # Application pages
│   ├── DashboardLive.tsx
│   ├── EventsLogs.tsx
│   ├── Reports.tsx
│   └── Planning.tsx
├── services/            # API service layer
│   └── api.ts
├── types/               # TypeScript type definitions
│   └── api.ts
├── utils/               # Utility functions
│   └── formatters.ts
├── App.tsx              # Main application with navigation
├── main.tsx             # Application entry point
└── index.css            # Global styles
```

## Technology Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Lucide React** for icons
- Custom polling hooks for real-time updates
- No external charting libraries (built-in SVG charts)

## Development Notes

### Real-time Updates

The application uses polling to keep data synchronized:
- Dashboard state: 1 second interval
- Event log: 2 seconds interval
- Reports: 5 seconds interval

All polling automatically stops when components unmount to prevent memory leaks.

### Error Handling

The application gracefully handles:
- Network errors (backend unavailable)
- API errors (HTTP 4xx/5xx)
- Loading states
- Empty data states

### TypeScript

All API responses are fully typed. See `src/types/api.ts` for complete type definitions.

## Troubleshooting

### Backend Connection Issues

If you see "Backend unreachable" errors:
1. Verify the FastAPI backend is running
2. Check the `VITE_API_BASE_URL` in your `.env` file
3. Ensure no CORS issues (the backend should allow requests from the frontend origin)

### Simulation Not Starting

If "Start" doesn't work:
- Check that day_start and day_end are properly formatted
- Ensure compress_to_seconds and tick_seconds are positive numbers
- Verify the backend logs for any error messages

### Events Not Showing

If events aren't appearing:
- Check that the simulation is running
- Verify the event was sent successfully (look for success/error toast)
- Check the Events & Logs page for the complete event history

## License

This project is part of the TECPAP Scheduler system.
