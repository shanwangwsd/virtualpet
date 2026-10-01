# Replace Your Pet, Food, and Toy Images

Resource root: `watch/HabitPet/Assets/` in the virtualpet project.

```
Assets/
  catalog.json
  Pets/
    Potato/potato_normal.png
    Cat/cat_normal.png
  Food/food_apple.png
  Toys/toy_ball.png
```

Both pets have slots for normal, happy, sad, angry, sick, dead, eat, drink, play, and rest. All PNG files are intentionally empty placeholders, not finished artwork. Cat uses your images too; there is no built-in cat drawing.

1. Export your art as a valid PNG, preferably with transparency and a consistent square canvas (256–512 px is sufficient for Watch display).
2. Replace the matching empty file, keeping its exact lowercase filename. For example replace `Pets/Potato/potato_drink.png` to change Potato's drinking image.
3. Replace `cat_*.png` with your own second character's artwork. The folder/ID is a resource identifier and does not force the image to depict a cat.
4. Rebuild and install the Watch app. Assets are bundled at build time, not downloaded at runtime.

An empty, missing, or unreadable state falls back to that species' normal image. If normal is also unavailable, the app shows “Image not added.” It will not fabricate another pet. Images are cached to avoid repeated disk reads during UI updates.

Current items: food_apple, food_carrot, food_meal, toy_ball, toy_yarn, toy_teddy. Replace their PNGs in Food/ or Toys/.

For expansion, add a new unique stable item ID and metadata in `catalog.json`, then its image file. Both backend and Watch read this same catalog. Do not reuse or remove an item ID that already appears in inventory; retain old catalog entries for old stock. New pet catalog entries also need the backend species allowlist extended. All page rendering uses the catalog, not scattered filenames.

The raw Assets folder is an Xcode folder resource, so new PNGs beneath it are bundled automatically. Do not place zero-byte PNGs inside an asset catalog imageset; this project deliberately loads these raw files with a safe missing-image fallback.
