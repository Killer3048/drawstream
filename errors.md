Log after cleanup (warnings removed):

$ python main.py
2025-10-27T13:04:12 | INFO | draw_stream.artistry.pixel_generator | pixel_generator.init
[diffusers progress bar]
2025-10-27T13:04:32 | INFO | draw_stream.donation.ingestor | ingestor.starting
Console commands:
  donate <amount> <message>
  da <amount> <message>
  exit|quit
Simulated DA donation: 5 USD – привет нарисуй замок
2025-10-27T13:04:33 | INFO | draw_stream.donation.ingestor | ingestor.stopping
2025-10-27T13:04:33 | INFO | draw_stream.donation.ingestor | ingestor.stopped

No `pkg_resources` / `diffusers` deprecation warnings, and stopping no longer prints uvicorn stacktraces.
