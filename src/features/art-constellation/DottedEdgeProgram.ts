import { EdgeProgram, type ProgramInfo } from "sigma/rendering";
import type { EdgeDisplayData, NodeDisplayData, RenderParams } from "sigma/types";
import { floatColor } from "sigma/utils";

const DOTS_PER_EDGE = 18;
const UNIFORMS = ["u_matrix", "u_pixelRatio"] as const;

const VERTEX_SHADER = /* glsl */ `
attribute vec4 a_id;
attribute vec4 a_color;
attribute vec2 a_position;
attribute float a_size;

uniform mat3 u_matrix;
uniform float u_pixelRatio;

varying vec4 v_color;

const float bias = 255.0 / 254.0;

void main() {
  gl_Position = vec4((u_matrix * vec3(a_position, 1.0)).xy, 0.0, 1.0);
  gl_PointSize = a_size * u_pixelRatio;

  #ifdef PICKING_MODE
  v_color = a_id;
  #else
  v_color = a_color;
  #endif

  v_color.a *= bias;
}
`;

const FRAGMENT_SHADER = /* glsl */ `
precision mediump float;

varying vec4 v_color;

void main() {
  if (distance(gl_PointCoord, vec2(0.5)) > 0.48) discard;
  gl_FragColor = v_color;
}
`;

/** Renders a C-level curatorial comparison as discrete round marks. */
export class DottedEdgeProgram extends EdgeProgram<(typeof UNIFORMS)[number]> {
  getDefinition() {
    return {
      VERTICES: DOTS_PER_EDGE,
      VERTEX_SHADER_SOURCE: VERTEX_SHADER,
      FRAGMENT_SHADER_SOURCE: FRAGMENT_SHADER,
      METHOD: WebGLRenderingContext.POINTS,
      UNIFORMS,
      ATTRIBUTES: [
        { name: "a_position", size: 2, type: WebGLRenderingContext.FLOAT },
        { name: "a_color", size: 4, type: WebGLRenderingContext.UNSIGNED_BYTE, normalized: true },
        { name: "a_id", size: 4, type: WebGLRenderingContext.UNSIGNED_BYTE, normalized: true },
        { name: "a_size", size: 1, type: WebGLRenderingContext.FLOAT },
      ],
    };
  }

  processVisibleItem(
    edgeIndex: number,
    startIndex: number,
    sourceData: NodeDisplayData,
    targetData: NodeDisplayData,
    data: EdgeDisplayData,
  ) {
    const color = floatColor(data.color);
    for (let index = 0; index < DOTS_PER_EDGE; index += 1) {
      const position = (index + 1) / (DOTS_PER_EDGE + 1);
      this.array[startIndex++] = sourceData.x + (targetData.x - sourceData.x) * position;
      this.array[startIndex++] = sourceData.y + (targetData.y - sourceData.y) * position;
      this.array[startIndex++] = color;
      this.array[startIndex++] = edgeIndex;
      this.array[startIndex++] = data.size;
    }
  }

  setUniforms({ matrix, pixelRatio }: RenderParams, { gl, uniformLocations }: ProgramInfo) {
    gl.uniformMatrix3fv(uniformLocations.u_matrix, false, matrix);
    gl.uniform1f(uniformLocations.u_pixelRatio, pixelRatio);
  }
}
