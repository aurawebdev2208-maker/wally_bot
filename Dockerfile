# Base image Node.js LTS (Debian Slim para compatibilidad total con binarios nativos, FFmpeg y ONNX Runtime)
FROM node:20-slim

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg, curl, tzdata)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=America/Argentina/Jujuy

# Copy package files
COPY package*.json ./

# Install production dependencies
RUN npm ci --only=production

# Copy application source code
COPY . .

# Create persistent folders
RUN mkdir -p /app/auth_info_baileys /app/.cache_models

# Expose port
EXPOSE 3000

# Environment defaults
ENV PORT=3000
ENV NODE_ENV=production

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# Start command
CMD ["node", "src/server.js"]
