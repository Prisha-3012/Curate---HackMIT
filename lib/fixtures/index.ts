import { bostonFixture } from "./boston";
import { campingFixture } from "./camping";
export const fixtures = [bostonFixture, campingFixture];
export const defaultFixture = bostonFixture;
export function findFixture(id: string | null) {
  return fixtures.find((fixture) => fixture.id === id) ?? defaultFixture;
}
