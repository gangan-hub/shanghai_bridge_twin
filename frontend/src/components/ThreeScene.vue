<template>
  <div ref="rootRef" class="root"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import * as THREE from "three";

const rootRef = ref(null);

let renderer;
let scene;
let camera;
let frameId = 0;

function setup() {
  const el = rootRef.value;
  const width = el.clientWidth || 300;
  const height = el.clientHeight || 220;

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height);
  el.appendChild(renderer.domElement);

  scene = new THREE.Scene();

  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 2000);
  camera.position.set(2.2, 1.6, 3.2);

  const ambient = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambient);

  const dir = new THREE.DirectionalLight(0xffffff, 0.9);
  dir.position.set(3, 4, 2);
  scene.add(dir);

  const grid = new THREE.GridHelper(6, 12, 0x334155, 0x1f2937);
  scene.add(grid);

  const geom = new THREE.BoxGeometry(1.2, 0.2, 0.4);
  const mat = new THREE.MeshStandardMaterial({ color: 0x2b6cb0, metalness: 0.2, roughness: 0.4 });
  const bridgeMock = new THREE.Mesh(geom, mat);
  bridgeMock.position.set(0, 0.2, 0);
  scene.add(bridgeMock);

  const towerGeom = new THREE.BoxGeometry(0.12, 0.9, 0.12);
  const towerMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.1, roughness: 0.8 });
  const t1 = new THREE.Mesh(towerGeom, towerMat);
  const t2 = new THREE.Mesh(towerGeom, towerMat);
  t1.position.set(-0.35, 0.55, 0);
  t2.position.set(0.35, 0.55, 0);
  scene.add(t1, t2);

  const cableMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55 });
  const cablePoints = [
    new THREE.Vector3(-0.6, 0.28, 0.0),
    new THREE.Vector3(-0.35, 1.0, 0.0),
    new THREE.Vector3(0.6, 0.28, 0.0),
    new THREE.Vector3(0.35, 1.0, 0.0),
  ];
  const geo1 = new THREE.BufferGeometry().setFromPoints([cablePoints[0], cablePoints[1]]);
  const geo2 = new THREE.BufferGeometry().setFromPoints([cablePoints[2], cablePoints[3]]);
  scene.add(new THREE.Line(geo1, cableMat));
  scene.add(new THREE.Line(geo2, cableMat));

  function renderLoop() {
    bridgeMock.rotation.y += 0.006;
    renderer.render(scene, camera);
    frameId = window.requestAnimationFrame(renderLoop);
  }
  renderLoop();

  const ro = new ResizeObserver(() => {
    const w = el.clientWidth || width;
    const h = el.clientHeight || height;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  ro.observe(el);

  return () => ro.disconnect();
}

let teardownResize = null;
onMounted(() => {
  teardownResize = setup();
});

onBeforeUnmount(() => {
  if (frameId) cancelAnimationFrame(frameId);
  if (teardownResize) teardownResize();
  if (renderer) {
    renderer.dispose();
    renderer.domElement?.remove();
  }
  renderer = null;
  scene = null;
  camera = null;
});
</script>

<style scoped>
.root {
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.65), rgba(2, 6, 23, 0.9));
}
</style>

