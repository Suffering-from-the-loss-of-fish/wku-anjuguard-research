import hashlib
import http.server
from pathlib import Path
import tempfile
import threading
import unittest

import numpy as np

from pilot.d2_data import ROOT, box_pixel_support, choose_frame_indices, contiguous_events, depth_points_world, download_ranges, rotate_bbox


class SourceTimingTests(unittest.TestCase):
    def test_preserves_actual_source_timestamps_and_handles_gaps(self):
        values = [5.125, 5.6, 6.13, 6.9, 8.25, 8.26, 9.13]
        chosen = choose_frame_indices(values)
        self.assertEqual(chosen, [0, 2, 4, 6])
        self.assertEqual([values[i] for i in chosen], [5.125, 6.13, 8.25, 9.13])

    def test_empty_input(self):
        self.assertEqual(choose_frame_indices([]), [])


class GeometryTests(unittest.TestCase):
    def test_inverse_extrinsic_and_measured_depth_support(self):
        depth = np.ones((8, 10))
        k = np.array([[10., 0, 5], [0, 10., 4], [0, 0, 1.]])
        extrinsic = np.eye(4)
        extrinsic[:3, 3] = [2., 0, 0]
        xyz, xx, yy = depth_points_world(depth, k, extrinsic)
        center_pixel = np.where((xx == 5) & (yy == 4))[0][0]
        np.testing.assert_allclose(xyz[center_pixel], [-2., 0, 1])
        annotation = {"segments": {"obbAligned": {"centroid": [-2, 0, 1], "axesLengths": [2, 2, .1], "normalizedAxes": np.eye(3).reshape(-1).tolist()}}}
        result = box_pixel_support(xyz, xx, yy, annotation, 10, 8)
        self.assertEqual(result["bbox"], [0., 0., 1., 1.])
        self.assertEqual(result["support_depth_points"], 80)
        annotation["segments"]["obbAligned"]["centroid"] = [20, 0, 1]
        self.assertIsNone(box_pixel_support(xyz, xx, yy, annotation, 10, 8))

    def test_bbox_rotation_matches_display_matrix(self):
        box = [.1, .2, .4, .7]
        np.testing.assert_allclose(rotate_bbox(box, -90), [.3, .1, .8, .4])
        np.testing.assert_allclose(rotate_bbox(rotate_bbox(box, -90), 90), box)
        with self.assertRaises(ValueError):
            rotate_bbox(box, 20)


class EventBoundaryTests(unittest.TestCase):
    def test_gaps_are_not_invented_and_last_end_is_capped(self):
        observations = [dict(object_uid="x", video_id="v", visit_id="site", split="dev", frame_id=f"f{i}", pts_s=t, class_name="chair", original_class="chair", bbox=[0, 0, .5, .5], support_depth_points=30) for i, t in enumerate([0., 1., 4.])]
        events = contiguous_events(observations, 4.25)
        self.assertEqual([(e["start_s"], e["end_s"]) for e in events], [(0., 2.), (4., 4.25)])
        self.assertTrue(all(e["review_status"] == "pending" for e in events))
        self.assertTrue(all(e["first_sufficiently_judgable_s"] is None for e in events))


class DownloadTests(unittest.TestCase):
    def test_byte_range_resume_reassembles_exact_source(self):
        payload = bytes(range(256)) * 11
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Length", len(payload))
                self.end_headers()
            def do_GET(self):
                lo, hi = map(int, self.headers["Range"].removeprefix("bytes=").split("-"))
                part = payload[lo:hi + 1]
                self.send_response(206)
                self.send_header("Content-Length", len(part))
                self.send_header("Content-Range", f"bytes {lo}-{hi}/{len(payload)}")
                self.end_headers()
                self.wfile.write(part)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            (ROOT / "runs/d2_data").mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT / "runs/d2_data") as directory:
                path = Path(directory) / "test.mov"
                path.with_suffix(".mov.partial").write_bytes(payload[:45])
                result = download_ranges(f"http://127.0.0.1:{server.server_port}/test", path, 2, 128)
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(result["resumed_prefix_bytes"], 45)
                self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
