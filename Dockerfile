# Base image Node.js LTS
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install build dependencies if needed
RUN apk add --no-cache tzdata

# Set timezone
ENV TZ=America/Argentina/Jujuy

# Copy package files
COPY package*.json ./

# Install production dependencies
RUN npm ci --only=production

# Copy application source code
COPY . .

# Create persistent folders
RUN mkdir -p /app/auth_info_baileys

# Expose port
EXPOSE 3000

# Environment defaults
ENV PORT=3000
ENV NODE_ENV=production

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

# Start command
CMD ["node", "src/server.js"]
