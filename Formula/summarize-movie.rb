class SummarizeMovie < Formula
  desc "CLI tool to summarize videos and generate meeting notes"
  homepage "https://github.com/Aosanori/summarizing-movie"
  url "https://github.com/Aosanori/summarizing-movie/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER"
  license "MIT"
  head "https://github.com/Aosanori/summarizing-movie.git", branch: "main"

  depends_on "python@3.12"
  depends_on "ffmpeg"
  depends_on :macos
  depends_on arch: :arm64

  def install
    # Copy source into libexec so post_install can pip-install from it.
    (libexec/"src").install Dir["*"]

    (bin/"summarize-movie").write <<~EOS
      #!/bin/bash
      exec "#{libexec}/venv/bin/summarize-movie" "$@"
    EOS
  end

  def post_install
    # Create virtualenv and pip-install here so that Homebrew's Mach-O
    # relocation step (which runs between install and post_install) never
    # touches the native .so files inside the venv.
    venv = libexec/"venv"
    system Formula["python@3.12"].opt_bin/"python3.12", "-m", "venv", venv
    system venv/"bin/pip", "install", "--upgrade", "pip"
    system venv/"bin/pip", "install", "--no-cache-dir", libexec/"src"
  end

  def caveats
    <<~EOS
      summarize-movie requires:
        1. LM Studio running locally (https://lmstudio.ai/)
           Start the local server at http://localhost:1234
        2. FFmpeg (installed as dependency)

      This tool is optimized for Apple Silicon (M1/M2/M3/M4).

      For speaker diarization (--diarize), install optional dependencies:
        #{libexec}/venv/bin/pip install pyannote.audio torch torchaudio
    EOS
  end

  test do
    assert_match "Usage", shell_output("#{bin}/summarize-movie --help")
    assert_match version.to_s, shell_output("#{bin}/summarize-movie --version")
  end
end
