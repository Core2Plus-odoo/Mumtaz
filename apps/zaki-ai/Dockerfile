FROM node:20-alpine

# Security: non-root user
RUN addgroup -S mumtaz && adduser -S mumtaz -G mumtaz

WORKDIR /app

# Install dependencies first (layer caching)
COPY package*.json ./
RUN npm ci --omit=dev

# Copy application
COPY --chown=mumtaz:mumtaz . .

USER mumtaz

EXPOSE 3000

CMD ["node", "server.js"]
