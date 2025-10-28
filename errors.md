(draw-stream-py3.11) vem@DESKTOP-5LSGHI7:/mnt/c/draw_stream$ python main.py
2025-10-27T20:34:06 | INFO | draw_stream.artistry.pixel_generator | pixel_generator.init
Loading pipeline components...: 100%|█████████████████████████████████████████████████████| 7/7 [00:14<00:00,  2.10s/it]
2025-10-27T20:34:27 | INFO | draw_stream.donation.ingestor | ingestor.starting
Console commands:
  donate <amount> <message>    # enqueue manual test donation
  da <amount> <message>         # simulate Donation Alerts event
  exit|quit                     # stop the stream

2025-10-27T20:34:28 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
da 1000 хуй в жопе
Simulated DA donation: 1000 USD – хуй в жопе
da 1000 красный крест
Simulated DA donation: 1000 USD – красный крест
da 1000 синий смурфик
Simulated DA donation: 1000 USD – синий смурфитк
da 1000 зеленый слоник
Simulated DA donation: 1000 USD – зеленый слоник
da 1000 Сил2025-10-27T20:34:59 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
ьный а2025-10-27T20:35:00 | INFO | httpx | HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions "HTTP/1.1 200 OK"
2025-10-27T20:35:00 | INFO | draw_stream.artistry.pipeline | scene.planned
2025-10-27T20:35:00 | INFO | draw_stream.artistry.pipeline | scene.rejected
2025-10-27T20:35:00 | INFO | draw_stream.app | queue.enqueued
ниме-персонаж
Simulated DA donation: 1000 USD – Сильный аниме-персонаж
2025-10-27T20:35:03 | INFO | httpx | HTTP Request: POST http://127.0.0.1:11434/v1/chat/completions "HTTP/1.1 200 OK"
2025-10-27T20:35:03 | INFO | draw_stream.artistry.pipeline | scene.planned
da 1000 морская звезда снимает с себя штаны
Simulated DA donation: 1000 USD – морская звезда снимает с себя штаны
da 1000 Удачного стрима. Кушай и наслаждай2025-10-27T20:35:23 | INFO | draw_stream.app | queue.enqueued
ся
Simulated DA donation: 1000 USD – Удачного стрима. Кушай и наслаждайся
2025-10-27T20:35:30 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:36:01 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
da 1000 Миньоны катаются на карусели
Unknown command. Use 'donate <amount> <message>' or 'quit'.
da 1000 Миньоны катаются на карусели
Simulated DA donation: 1000 USD – Миньоны катаются на карусели
2025-10-27T20:36:32 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:37:04 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:37:35 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:38:06 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:38:37 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:39:08 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:39:39 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
da 1000 миьоны на карусели
Unknown command. Use 'donate <amount> <message>' or 'quit'.
da 1000 Миньоны на карусели
Simulated DA donation: 1000 USD – Миньоны на карусели
2025-10-27T20:40:11 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
2025-10-27T20:40:42 | INFO | httpx | HTTP Request: GET https://www.donationalerts.com/api/v1/alerts/donations?limit=10 "HTTP/1.1 200 OK"
^Cexit
Traceback (most recent call last):
  File "/mnt/c/draw_stream/main.py", line 19, in <module>
    asyncio.run(run_app())
  File "/home/vem/.pyenv/versions/3.11.13/lib/python3.11/asyncio/runners.py", line 190, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/home/vem/.pyenv/versions/3.11.13/lib/python3.11/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/vem/.pyenv/versions/3.11.13/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/mnt/c/draw_stream/src/draw_stream/main.py", line 82, in main
    await app.stop()
  File "/mnt/c/draw_stream/src/draw_stream/app.py", line 62, in stop
    await self._worker_task
  File "/mnt/c/draw_stream/src/draw_stream/app.py", line 96, in _worker_loop
    await self._handle_event(event)
  File "/mnt/c/draw_stream/src/draw_stream/app.py", line 104, in _handle_event
    plan = await self._orchestrator.generate_plan(event)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/c/draw_stream/src/draw_stream/llm.py", line 24, in generate_plan
    return await self._pipeline.create_plan(event)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/c/draw_stream/src/draw_stream/artistry/pipeline.py", line 38, in create_plan
    scene_plan = await self._scene_planner.describe(event)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mnt/c/draw_stream/src/draw_stream/artistry/scene_planner.py", line 121, in describe
    response = await self._client.post(
               ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/lib/python3.11/site-packages/httpx/_client.py", line 1859, in post
    return await self.request(
           ^^^^^^^^^^^^^^^^^^^
  File "/home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/lib/python3.11/site-packages/httpx/_client.py", line 1527, in request
    request = self.build_request(
              ^^^^^^^^^^^^^^^^^^^
  File "/home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/lib/python3.11/site-packages/httpx/_client.py", line 378, in build_request
    return Request(
           ^^^^^^^^
  File "/home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/lib/python3.11/site-packages/httpx/_models.py", line 408, in __init__
    headers, stream = encode_request(
                      ^^^^^^^^^^^^^^^
  File "/home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/lib/python3.11/site-packages/httpx/_content.py", line 216, in encode_request
    return encode_json(json)
           ^^^^^^^^^^^^^^^^^
  File "/home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/lib/python3.11/site-packages/httpx/_content.py", line 179, in encode_json
    ).encode("utf-8")
      ^^^^^^^^^^^^^^^
UnicodeEncodeError: 'utf-8' codec can't encode character '\udcd1' in position 2898: surrogates not allowed
(draw-stream-py3.11) vem@DESKTOP-5LSGHI7:/mnt/c/draw_stream$