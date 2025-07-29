# PiggyGoUp

PiggyGoUp lets you watch your savings balance tick up in real time using data from your bank via [TrueLayer](https://truelayer.com/).

## Setup

1. Create a TrueLayer account and obtain sandbox credentials.
2. Set the following environment variables:

```
TRUELAYER_CLIENT_ID=your_client_id
TRUELAYER_CLIENT_SECRET=your_client_secret
TRUELAYER_REDIRECT_URI=http://localhost:5000/callback
FLASK_SECRET_KEY=change-me
```

3. Install dependencies:

```
pip install flask requests
```

4. Run the server:

```
python piggygoup/backend/app.py
```

5. Open `http://localhost:5000` in your browser and click "Connect Bank Account".

## Production

For production usage, use your live TrueLayer credentials and update `TRUELAYER_URL` to `https://auth.truelayer.com`.
Store tokens securely (e.g. database or encrypted storage) and deploy behind HTTPS.

## Notes

This project is intentionally simple and focuses on core functionality: TrueLayer OAuth, a balance API, and a frontend that displays an interpolated, continuously growing balance with milestone celebrations. Feel free to extend it with more gamification features!
