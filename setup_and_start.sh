# Download and configure FFmpeg
echo "Setting up FFmpeg..."
mkdir -p /tmp/ffmpeg_setup
cd /tmp/ffmpeg_setup
curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
FFMPEG_DIR=$(ls | grep ffmpeg-master)
mkdir -p ~/.local/bin
cp ${FFMPEG_DIR}/bin/ffmpeg ~/.local/bin/
chmod +x ~/.local/bin/ffmpeg
export PATH="~/.local/bin:$PATH"
cd -
rm -rf /tmp/ffmpeg_setup

echo "FFmpeg installed at $(which ffmpeg):"
~/.local/bin/ffmpeg -version

# Start the bot
echo "Starting TuneCast bot..."
python tunecast.py
