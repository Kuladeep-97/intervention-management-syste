import cv2
import json
import numpy as np
import time
import math
import os
from app.pipeline.onnx_engine import ONNXEngine

class PipelineProcessor:
    def __init__(self, model_path: str, ports_json: str):
        # Configuration
        self.INTERSECTION_THRESHOLD = 50
        self.PANEL_WIDTH = 450
        self.MOTION_THRESHOLD_PX = 15
        self.STATIC_TIME_SEC = 3.0
        self.MAX_REACH_DISTANCE = 250
        self.MIN_GLOVE_AREA_PX = 100
        self.SESSION_GRACE_PERIOD_SEC = 5.0
        self.MIN_SESSION_DURATION_SEC = 1.0

        self.PORT_COLORS = {
            "port_1": (0, 0, 255),
            "port_2": (0, 255, 0),
            "port_3": (255, 0, 0),
            "port_4": (0, 255, 255),
            "port_5": (255, 0, 255),
            "port_6": (0, 165, 255),
            "port_7": (200, 255, 100),
            "port_8": (255, 255, 0)
        }

        print("Initializing Advanced Analytics Pipeline...")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model {model_path} not found.")
        if not os.path.exists(ports_json):
            raise FileNotFoundError(f"{ports_json} not found.")
            
        from ultralytics import YOLO
        self.model = YOLO(model_path, task='segment')

        with open(ports_json, 'r') as f:
            self.ports_data = json.load(f)

        self.fixed_port_masks = {}
        self.port_centroids = {}
        # Assume max 1080p for mask init, will adjust if needed dynamically
        # But for robust design, it's better to compute on the first frame if resolution varies.
        # We will compute these dynamically in process_stream once we know the width/height
        
        # State Trackers
        self.next_glove_id = 1
        self.tracked_gloves = {}
        self.glove_motion_state = {}
        self.active_sessions = {}
        self.intervention_counters = {}
        self.completed_sessions = []
        self.port_polygon_history = {}
        
        self.frame_count = 0
        self.metrics = {"in_count": 0, "out_count": 0, "active_objects": 0}

    def compute_port_masks(self, width, height):
        self.fixed_port_masks = {}
        self.port_centroids = {}
        for port_name, coords in self.ports_data.items():
            mask = np.zeros((height, width), dtype=np.uint8)
            pts = np.array(coords, dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
            self.fixed_port_masks[port_name] = mask
            
            pM = cv2.moments(pts)
            if pM["m00"] != 0:
                pcx = int(pM["m10"] / pM["m00"])
                pcy = int(pM["m01"] / pM["m00"])
            else:
                pcx, pcy = pts[0][0], pts[0][1]
            self.port_centroids[port_name] = (pcx, pcy)

    def process_stream(self, frame_generator, fps):
        """
        Takes an iterator of frames and yields (processed_frame, metrics_dict)
        """
        masks_computed = False
        
        for frame in frame_generator:
            height, width = frame.shape[:2]
            
            if not masks_computed:
                self.compute_port_masks(width, height)
                masks_computed = True
                
            timestamp = self.frame_count / fps
            
            # --- Temporal Subsampling ---
            # Process 1 in every 2 frames to restore visual smoothness
            if self.frame_count % 2 == 0 or not hasattr(self, 'last_results'):
                self.last_results = self.model.predict(frame, imgsz=320, conf=0.15, retina_masks=False, verbose=False)[0]
            
            results = self.last_results
            
            overlay = frame.copy()
            glove_polygons = []
            current_gloves = []
            
            if results.masks is not None:
                for i, mask_xy in enumerate(results.masks.xy):
                    poly = np.array(mask_xy, dtype=np.int32)
                    if cv2.contourArea(poly) < self.MIN_GLOVE_AREA_PX:
                        continue
                        
                    M = cv2.moments(poly)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = poly[0][0], poly[0][1]
                    current_gloves.append((cx, cy, poly))

            new_tracked_gloves = {}
            glove_ids = []
            
            for (cx, cy, poly) in current_gloves:
                best_id = None
                min_dist = 100
                for t_id, (t_cx, t_cy) in self.tracked_gloves.items():
                    dist = math.hypot(cx - t_cx, cy - t_cy)
                    if dist < min_dist:
                        min_dist = dist
                        best_id = t_id
                
                if best_id is not None:
                    g_id = best_id
                    del self.tracked_gloves[best_id]
                else:
                    g_id = self.next_glove_id
                    self.next_glove_id += 1
                    
                new_tracked_gloves[g_id] = (cx, cy)
                glove_ids.append(g_id)
                glove_polygons.append(poly)
                
                if g_id not in self.glove_motion_state:
                    self.glove_motion_state[g_id] = {"last_cx": cx, "last_cy": cy, "last_moved_time": timestamp, "is_moving": True}
                else:
                    state = self.glove_motion_state[g_id]
                    dist = math.hypot(cx - state["last_cx"], cy - state["last_cy"])
                    if dist > self.MOTION_THRESHOLD_PX:
                        state["last_cx"] = cx
                        state["last_cy"] = cy
                        state["last_moved_time"] = timestamp
                        state["is_moving"] = True
                    else:
                        if (timestamp - state["last_moved_time"]) > self.STATIC_TIME_SEC:
                            state["is_moving"] = False
                        else:
                            state["is_moving"] = True

            self.tracked_gloves = new_tracked_gloves
            
            current_frame_glove_ports = {}
            occupied_ports = set()
            
            for g_id, poly in zip(glove_ids, glove_polygons):
                glove_mask = np.zeros((height, width), dtype=np.uint8)
                cv2.fillPoly(glove_mask, [poly], 255)
                
                best_port = None
                max_overlap = self.INTERSECTION_THRESHOLD
                
                for port_name, mask in self.fixed_port_masks.items():
                    overlap = cv2.bitwise_and(mask, glove_mask)
                    overlap_count = cv2.countNonZero(overlap)
                    if overlap_count > max_overlap:
                        max_overlap = overlap_count
                        best_port = port_name
                        
                if not best_port:
                    min_dist = float('inf')
                    pts = poly.reshape(-1, 2)
                    for port_name, (pcx, pcy) in self.port_centroids.items():
                        dists = np.sqrt((pts[:, 0] - pcx)**2 + (pts[:, 1] - pcy)**2)
                        dist = np.min(dists)
                        if port_name in self.active_sessions:
                            dist = dist * 0.2
                        if dist < min_dist:
                            min_dist = dist
                            best_port = port_name
                    if min_dist > self.MAX_REACH_DISTANCE * 2:
                        best_port = None
                        
                if best_port:
                    current_frame_glove_ports[g_id] = best_port
                    occupied_ports.add(best_port) 

            current_active_gloves = set()
            current_static_gloves = set()
            
            for g_id, poly in zip(glove_ids, glove_polygons):
                best_port = current_frame_glove_ports.get(g_id)
                if best_port:
                    is_moving = self.glove_motion_state.get(g_id, {}).get("is_moving", True)
                    if is_moving:
                        current_active_gloves.add((best_port, g_id))
                        color = self.PORT_COLORS.get(best_port, (0, 255, 0))
                        cv2.fillPoly(overlay, [poly], color)
                    else:
                        current_static_gloves.add((best_port, g_id))
                        base_color = self.PORT_COLORS.get(best_port, (0, 255, 0))
                        dim_color = (int(base_color[0]*0.4), int(base_color[1]*0.4), int(base_color[2]*0.4))
                        cv2.fillPoly(overlay, [poly], dim_color)
                else:
                    cv2.fillPoly(overlay, [poly], (200, 200, 200))

            current_occupied_ports = set(current_frame_glove_ports.values())
            ended_ports = []
            
            for session_port, session in self.active_sessions.items():
                if session_port not in current_occupied_ports:
                    if (timestamp - session["last_seen"]) > self.SESSION_GRACE_PERIOD_SEC:
                        session["end_time"] = session["last_seen"]
                        if session["total_duration"] >= self.MIN_SESSION_DURATION_SEC:
                            self.completed_sessions.insert(0, session)
                            self.metrics["out_count"] += 1
                        ended_ports.append(session_port)
                    else:
                        session["active_duration"] += (timestamp - session["last_timestamp"])
                        session["last_timestamp"] = timestamp 
                        session["total_duration"] = session["active_duration"] + session["idle_duration"]
                        if session_port in self.port_polygon_history:
                            self.port_polygon_history[session_port]["frames_missed"] += 1
                else:
                    session["last_seen"] = timestamp
                    g_ids = [g for g, p in current_frame_glove_ports.items() if p == session_port]
                    if g_ids:
                        idx = glove_ids.index(g_ids[0])
                        poly = glove_polygons[idx]
                        self.port_polygon_history[session_port] = {"poly": poly, "frames_missed": 0, "color": self.PORT_COLORS.get(session_port, (0, 255, 0))}
                        g_id_str = session_port.split('_')[-1]
                        session["glove_id"] = g_id_str
                        is_moving = any(self.glove_motion_state.get(g, {}).get("is_moving", True) for g in g_ids)
                        if is_moving:
                            session["active_duration"] += (timestamp - session["last_timestamp"])
                        else:
                            session["idle_duration"] += (timestamp - session["last_timestamp"])
                    session["last_timestamp"] = timestamp
                    session["total_duration"] = session["active_duration"] + session["idle_duration"]

            for p in ended_ports:
                del self.active_sessions[p]

            for port_name in current_occupied_ports:
                if port_name not in self.active_sessions:
                    self.intervention_counters[port_name] = self.intervention_counters.get(port_name, 0) + 1
                    inv_num = self.intervention_counters[port_name]
                    g_id_str = port_name.split('_')[-1]
                    self.active_sessions[port_name] = {
                        "port_name": port_name,
                        "glove_id": g_id_str,
                        "start_time": timestamp,
                        "last_seen": timestamp,
                        "last_timestamp": timestamp,
                        "active_duration": 0.0,
                        "idle_duration": 0.0,
                        "total_duration": 0.0,
                        "intervention_num": inv_num
                    }
                    self.metrics["in_count"] += 1

            active_ports_only = {p for p, g in current_active_gloves}
            static_ports_only = {p for p, g in current_static_gloves}

            for session_port in self.active_sessions:
                if session_port not in active_ports_only and session_port not in static_ports_only:
                    active_ports_only.add(session_port)

            for port_name, coords in self.ports_data.items():
                port_poly = np.array(coords, dtype=np.int32)
                if port_name in active_ports_only:
                    color = self.PORT_COLORS.get(port_name, (0, 255, 0))
                    cv2.fillPoly(overlay, [port_poly], color)
                elif port_name in static_ports_only:
                    base_color = self.PORT_COLORS.get(port_name, (0, 255, 0))
                    dim_color = (int(base_color[0]*0.3), int(base_color[1]*0.3), int(base_color[2]*0.3))
                    cv2.fillPoly(overlay, [port_poly], dim_color)
                else:
                    cv2.fillPoly(overlay, [port_poly], (30, 30, 30))

            main_feed = cv2.addWeighted(overlay, 0.40, frame, 0.60, 0)

            for g_id, poly in zip(glove_ids, glove_polygons):
                is_moving = self.glove_motion_state.get(g_id, {}).get("is_moving", True)
                found_port = None
                for p, g in current_active_gloves.union(current_static_gloves):
                    if g == g_id:
                        found_port = p
                        break
                if found_port:
                    base_color = self.PORT_COLORS.get(found_port, (0, 255, 0))
                    if is_moving:
                        cv2.polylines(main_feed, [poly], True, base_color, 2)
                    else:
                        dim_color = (int(base_color[0]*0.5), int(base_color[1]*0.5), int(base_color[2]*0.5))
                        cv2.polylines(main_feed, [poly], True, dim_color, 2)
                    M = cv2.moments(poly)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        display_id = found_port.split('_')[-1] if found_port else "?"
                        cv2.putText(main_feed, f"G:{display_id}", (cx-15, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2)
                else:
                    cv2.polylines(main_feed, [poly], True, (255, 255, 255), 1)

            for session_port in self.active_sessions:
                if session_port not in current_occupied_ports and session_port in self.port_polygon_history:
                    history = self.port_polygon_history[session_port]
                    frames_missed = history["frames_missed"]
                    if frames_missed <= 20: 
                        alpha = max(0.2, 0.8 - (frames_missed / 20.0))
                        color = history["color"]
                        fade_color = (int(color[0]*alpha), int(color[1]*alpha), int(color[2]*alpha))
                        cv2.polylines(main_feed, [history["poly"]], True, fade_color, 2)

            for port_name, coords in self.ports_data.items():
                port_poly = np.array(coords, dtype=np.int32)
                pcx, pcy = self.port_centroids[port_name]
                if port_name in active_ports_only:
                    color = self.PORT_COLORS.get(port_name, (0, 255, 0))
                    cv2.polylines(main_feed, [port_poly], True, color, 3)
                    cv2.putText(main_feed, f"{port_name} ACTIVE", (pcx - 40, pcy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                elif port_name in static_ports_only:
                    base_color = self.PORT_COLORS.get(port_name, (0, 255, 0))
                    dim_color = (int(base_color[0]*0.5), int(base_color[1]*0.5), int(base_color[2]*0.5))
                    cv2.polylines(main_feed, [port_poly], True, dim_color, 2)
                    cv2.putText(main_feed, f"{port_name} IDLE", (pcx - 50, pcy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, dim_color, 2)
                else:
                    cv2.polylines(main_feed, [port_poly], True, (150, 150, 150), 1)
                    cv2.putText(main_feed, port_name, (pcx - 20, pcy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

            self.frame_count += 1
            self.metrics["active_objects"] = len(self.tracked_gloves)
            
            yield main_feed, self.metrics.copy()
