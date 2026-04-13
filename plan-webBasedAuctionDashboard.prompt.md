## Plan: Web-based Auction Dashboard (FastAPI + React)

TL;DR: Re-architect the current threaded TCP socket auction (single process, in-memory state, text protocol) into a FastAPI-based backend exposing both REST and WebSocket interfaces, plus a React frontend that consumes initial auction state via HTTP and then stays in sync through structured WebSocket events.

**Current Architecture Analysis**
- Single TCP server in [server.py](server.py) listening on a fixed port, using threads per client plus one timer thread per auction item.
- Shared in-memory auction_items dict storing highest_bid, bidder, and time_left; synchronized with a global lock.
- Simple broadcast() function that pushes plain-text messages to all connected clients; protocol is implicit (human-readable strings) rather than structured.
- Timers implemented via blocking time.sleep in item_timer threads that decrement time_left and, at zero, broadcast winner/no-bid messages and final summary.
- Client in [client.py](client.py) is a console app with one background thread reading from the socket and a foreground loop reading user input and sending lines to the server.
- No separation of concerns (business logic vs transport), no persistence, no user identity beyond a name string, and limited scalability due to threading model, global state, and single-node design.

**Steps**
1. Backend domain & data model
   - Define core domain models (Auction, AuctionItem, Bid, UserSummary) as Pydantic models to decouple business logic from transport and ease validation.
   - Introduce an AuctionManager service responsible for holding auction state, validating bids, managing timers, and exposing methods like place_bid, get_state, tick_timers, and end_item.
   - For the first iteration, keep state in memory (similar to current dict) but structure it for easy later replacement with a database.

2. FastAPI backend structure
   - Create a FastAPI application (e.g., in app/main.py) with clear layering: routers (HTTP & WebSocket), services (AuctionManager), and models (Pydantic schemas).
   - Add REST endpoints for initial data loading and admin/introspection, such as:
     - GET /api/auctions - list active auctions (or a single default auction for now).
     - GET /api/auctions/{auction_id} - get full state (items, highest bids, time_left, winners if finished).
     - GET /api/auctions/{auction_id}/items/{item_id} - get item-specific details.
   - Optionally add simple mutation endpoints for admin use (e.g., POST /api/auctions to create an auction) while keeping bidder interactions via WebSockets.

3. WebSocket integration (backend)
   - Define a WebSocket endpoint, e.g., /ws/auctions/{auction_id}, that accepts connections from React clients.
   - On connect, authenticate or at least register the user (basic name string or ID for now), and subscribe the socket to that auction's broadcast group.
   - Define a structured JSON message protocol with fields like: { "type": "bid_placed" | "timer_update" | "auction_ended" | "state_snapshot" | "error", "payload": {...} }.
   - Implement server-side handlers for incoming events from clients:
     - bid.place: client sends { type: "place_bid", payload: { itemId, amount, bidderName } }.
     - optional join: client sends { type: "join", payload: { bidderName } } to register identity.
   - Wire WebSocket connections into AuctionManager so when a valid bid is placed, AuctionManager updates state and triggers a broadcast to all sockets in that auction.
   - Replace per-item threading with asyncio-based background tasks or a central scheduler that updates timers and emits timer_update and auction_ended events.

4. Frontend architecture (React)
   - Create a React SPA with a main layout that shows the current auction dashboard.
   - Structure components into:
     - App: routing, top-level providers (e.g., query client, auth context).
     - AuctionDashboard: displays a list/grid of auction items, user info, and global status.
     - AuctionItemCard: shows item name, current highest bid, highest bidder, and time remaining.
     - BidControls: allows user to enter a bid value or use preset increment buttons and submit.
     - TimerDisplay: visual countdown (numeric + progress bar or circular indicator).
     - Leaderboard: shows top bidders or winners per item after auctions end.
     - Notifications/Toasts: feedback for bid accepted/rejected, connection issues, auction end.
   - Use a state management approach such as:
     - React Query (TanStack Query) for initial HTTP data fetching (GET endpoints).
     - React context or a custom hook (e.g., useAuctionSocket) for WebSocket connection, event handling, and pushing real-time updates into component state.

5. Communication flow (end-to-end)
   - Initial load:
     - React loads /api/auctions (and /api/auctions/{auction_id}) to get initial list of items, current bids, and remaining time.
     - React establishes a WebSocket connection to /ws/auctions/{auction_id} and sends an optional join message with bidder name.
     - Backend responds over WebSocket with a state_snapshot event containing full auction state for that client to sync with HTTP-fetched data.
   - Real-time updates:
     - When a client places a bid, it sends place_bid over WebSocket.
     - Backend validates (auction not ended, bid > current highest_bid, etc.) via AuctionManager, updates state, and broadcasts a bid_placed event to all connected clients.
     - Timer updates are emitted regularly (e.g., every second or every few seconds) via timer_update events containing itemId and new time_left.
     - When an item finishes, AuctionManager emits auction_ended with winner and final bid; frontend marks that item as ended and optionally moves it to a "Completed" section.
   - Errors and edge cases:
     - Invalid bids result in error events (e.g., { type: "error", payload: { code, message } }) so UI can show inline messages.
     - Connection lost: frontend shows a connection status banner and attempts reconnection; on reconnect, backend sends a fresh state_snapshot.

6. Auction data model
   - Core entities (conceptual):
     - Auction: id, name, status (active/completed), startTime, endTime, list of AuctionItems.
     - AuctionItem: id, auctionId, name, description, startingPrice, highestBid, highestBidder, timeLeftSeconds, status (pending/active/completed).
     - Bid: id, itemId, bidderId or bidderName, amount, timestamp.
     - UserSummary (for UI only): bidderName, totalBids, totalAmount, lastBidTime.
   - In FastAPI, define Pydantic schemas for:
     - AuctionItemPublic: fields for the dashboard (excluding internal details).
     - AuctionState: auctionId, items: [AuctionItemPublic], serverTime for sync.
     - BidRequest: itemId, bidderName, amount.
     - BidEvent / TimerEvent / AuctionEndEvent: for WebSocket payloads.
   - Maintain state in AuctionManager similarly to current auction_items dict, but keyed by itemId and storing full objects rather than ad-hoc dicts; guard concurrent access using asyncio primitives.

7. Event flow definition
   - Bid placed:
     - Frontend: user clicks "Place Bid" with amount; component sends { type: "place_bid", payload: { itemId, amount, bidderName } } via WebSocket.
     - Backend: validates and, if accepted, updates AuctionItem.highestBid and highestBidder; emits { type: "bid_placed", payload: { itemId, highestBid, highestBidder } } to all sockets.
     - Frontend: updates specific item in local state and optionally animates the card or shows a toast.
   - Timer update:
     - Backend scheduler or item-specific task decrements timeLeftSeconds and, at configured intervals, broadcasts { type: "timer_update", payload: { itemId, timeLeftSeconds } }.
     - Frontend: TimerDisplay for that item interpolates smoothly and re-renders the countdown.
   - Auction end:
     - Backend: when timeLeftSeconds reaches 0, sets item.status = "completed", determines winner, and emits { type: "auction_ended", payload: { itemId, winnerName, finalBid } }.
     - Frontend: marks the item as completed, disables BidControls, and moves it to a "Completed" or "Results" section; Leaderboard updates with this result.

8. API endpoints
   - Read-only (for dashboard and SEO/crawlers if needed):
     - GET /api/auctions - list basic info about current and upcoming auctions.
     - GET /api/auctions/{auction_id} - full state snapshot including all items and bids summary.
     - GET /api/auctions/{auction_id}/items/{item_id} - details for one item.
   - Admin/management (optional, for future):
     - POST /api/auctions - create new auction.
     - POST /api/auctions/{auction_id}/items - add item.
     - POST /api/auctions/{auction_id}/start - start timers.
     - POST /api/auctions/{auction_id}/items/{item_id}/extend - extend time.
   - WebSocket:
     - ws://.../ws/auctions/{auction_id} - primary real-time channel.

9. UI feature suggestions
   - Live bidding controls:
     - For each AuctionItemCard, provide an input for custom bid amount and quick-increment buttons (e.g., +10, +50, +100) relative to the current highest bid.
     - Disable bid button when item has ended or when connection is lost.
   - Timer visualization:
     - Show both numeric countdown (mm:ss) and a progress bar indicating time remaining.
     - Color transitions (green → yellow → red) as time decreases.
   - Leaderboard / winners:
     - Global leaderboard summarizing top bidders by total amount or number of wins.
     - Per-item winner display once the auction ends, including final price and winner name.
   - User feedback:
     - Toasts/snackbar notifications for events like "Bid accepted", "Bid rejected: too low", "Auction ended", "Reconnecting...".
     - Connection status indicator (online/offline/reconnecting) at the top of the dashboard.

10. Step-by-step implementation plan
    - Step 1: Backend conversion
      - Extract auction logic from [server.py](server.py) into a dedicated AuctionManager class (domain service) with clear methods for place_bid, get_state, start_auction, and internal timer handling.
      - Define Pydantic models for AuctionItem, AuctionState, BidRequest, and event payloads.
      - Scaffold a FastAPI app with basic REST endpoints for GET /api/auctions and GET /api/auctions/{auction_id} returning data from AuctionManager.
    - Step 2: WebSocket integration
      - Add a WebSocket route (/ws/auctions/{auction_id}) to the FastAPI app.
      - Implement connection management (track connected clients per auction) and hook them into AuctionManager broadcasts.
      - Implement the JSON-based message protocol for place_bid, state_snapshot, timer_update, and auction_ended events.
      - Replace thread-based timers with asyncio background tasks scheduled via FastAPI's startup event or a dedicated background task manager.
    - Step 3: Frontend UI
      - Scaffold a React app (e.g., using Vite) and set up basic routing and layout for the auction dashboard.
      - Build core components: AuctionDashboard, AuctionItemCard, BidControls, TimerDisplay, Leaderboard, and Notifications.
      - Implement data fetching from the REST endpoints for initial state, using React Query or simple fetch logic.
      - Implement a custom hook (useAuctionSocket) that opens the WebSocket, handles reconnection, and exposes current auction state and actions (placeBid).
    - Step 4: Integration and refinement
      - Wire components to the useAuctionSocket hook so that real-time updates drive the UI state.
      - Add optimistic UI feedback for bids while still reconciling with server-confirmed events.
      - Test flows with multiple browser tabs to simulate multiple bidders; adjust event payloads and UI as needed.
      - Add basic error handling, logging, and configuration (e.g., environment-based API base URLs) for local and production environments.

**Relevant files**
- [server.py](server.py) — Reference for existing auction logic (bids, timers, broadcast) to be migrated into AuctionManager.
- [client.py](client.py) — Reference for current text protocol and client interactions when designing WebSocket message types.
- app/main.py (to be created) — FastAPI entrypoint defining the app, routers, and WebSocket endpoint.
- app/models.py (to be created) — Pydantic models for AuctionItem, AuctionState, BidRequest, and WebSocket events.
- app/services/auction_manager.py (to be created) — Core auction domain logic and state management.
- frontend/src/App.tsx or App.jsx (to be created) — Root React component and routing.
- frontend/src/components/* (to be created) — AuctionDashboard, AuctionItemCard, BidControls, TimerDisplay, Leaderboard, etc.

**Verification**
1. Manually test FastAPI endpoints via browser or a tool like curl/Postman to ensure initial auction state is exposed correctly.
2. Use a WebSocket client (e.g., browser dev tools or a test page) to verify that connecting, placing bids, and receiving timer_update and auction_ended events work as expected.
3. Run the React app against the local FastAPI backend; confirm that multiple browser tabs stay in sync when placing bids and that timers and results update in real time.
4. Perform basic load tests with multiple concurrent connections to check that the asyncio-based implementation handles concurrency more robustly than the original threaded version.

**Decisions**
- Use in-memory storage initially, mirroring your current design, with the architecture structured so that a database (e.g., PostgreSQL with SQLAlchemy) can be added later without changing the frontend or WebSocket protocol.
- Use structured JSON messages for WebSocket communication, replacing the unstructured text protocol, to make the system more maintainable and extensible.
- Keep authentication simple at first (bidderName passed from the client) but design the protocol so that real authentication (JWT/cookies) can be introduced later without breaking changes to event flow.
