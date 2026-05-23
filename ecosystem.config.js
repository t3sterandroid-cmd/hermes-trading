module.exports = {
  apps: [{
    name: "hermes-trading",
    script: "src/main.py",
    cwd: "/home/r00t/hermes-trading",
    interpreter: "/home/r00t/trading-env/bin/python3",
    env: { NODE_ENV: "production" },
    log_file: "logs/pm2.log",
    error_file: "logs/pm2-error.log",
    max_memory_restart: "512M",
    restart_delay: 5000,
    max_restarts: 10
  }]
};
