// PM2 process config
// Run: pm2 start ecosystem.config.js
// Run: pm2 save && pm2 startup

module.exports = {
  apps: [{
    name:        'zaki-ai',
    script:      'server.js',
    cwd:         '/var/www/zaki.mumtaz.digital',
    instances:   1,
    autorestart: true,
    watch:       false,
    max_memory_restart: '512M',
    env: {
      NODE_ENV:         'production',
      PORT:             3000,
    },
    error_file:  '/var/log/zaki/error.log',
    out_file:    '/var/log/zaki/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
  }],
};
