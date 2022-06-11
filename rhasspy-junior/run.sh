#!/usr/bin/with-contenv bashio
set -e

share_dir='/share/rhasspy-junior'
mkdir -p "${share_dir}"

cd /app

cat > junior.local.toml <<EOF
[train.home_assistant]
api_url = 'http://supervisor/core/api'
api_token = '${SUPERVISOR_TOKEN}'

[handle.home_assistant]
api_url = 'http://supervisor/core/api'
api_token = '${SUPERVISOR_TOKEN}'
EOF

echo 'Training'
scripts/train.sh \
    --user-data-dir "${share_dir}/data" \
    --user-train-dir "${share_dir}/train" \
    --debug \
    --config junior.local.toml

if [ ! -s "${share_dir}/train/home_assistant/sentences.ini" ]; then
	echo 'No entities found that can be controlled with voice commands';
	exit 1;
fi

echo 'Training complete. Running'
scripts/run.sh \
    --user-data-dir "${share_dir}/data" \
    --user-train-dir "${share_dir}/train" \
    --debug \
    --config junior.local.toml

