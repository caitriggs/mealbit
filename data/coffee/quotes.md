# Coffee Ritual — the quote pool

> last_updated: 2026-08-29
> One per newsletter, never repeated until the pool is exhausted (`history.json` tracks it).
>
> **The brief for this pool:** interesting, fun or weird, and pointed at *making* rather
> than *buying* — caffeine and cooking as things you do, not things you purchase.
>
> **`attribution:` is not decoration.** Half the famous coffee quotes on the internet are
> invented. Each entry is flagged so the newsletter can say so out loud:
> - `verified` — traceable to a published source
> - `attributed` — widely and plausibly credited, primary source not nailed down
> - `disputed` — commonly repeated, probably not said by that person
> - `legend` — a story, told as a story
> - `fiction` — from a novel or film, and labelled as such
> - `history` — not a quote at all; a true and weird thing that happened

```yaml
- text: "What I cannot create, I do not understand."
  who: Richard Feynman
  source: found on his blackboard at his death, February 1988
  attribution: verified
  note: >-
    The line was still on the board, under a heading that read "Know how to solve every
    problem that has been solved." A physicist's argument for cooking your own dinner.
  tags: [making, understanding]

- text: >-
    The cost of a thing is the amount of what I will call life which is required to be
    exchanged for it, immediately or in the long run.
  who: Henry David Thoreau
  source: Walden, 1854
  attribution: verified
  note: >-
    Thirty coffee-shop visits a month is a few hundred dollars. It is also about fifteen
    hours of standing in line.
  tags: [money, time, consuming]

- text: >-
    Coffee is a great power in my life... ideas quick-march into motion like battalions
    of a grand army to its legendary fighting ground, and the battle rages.
  who: Honoré de Balzac
  source: Traité des excitants modernes, 1839 (translated)
  attribution: verified
  note: >-
    Balzac also recommended eating dry ground coffee on an empty stomach for a stronger
    effect. He is not a role model in all respects.
  tags: [coffee, weird]

- text: >-
    Ah! How sweet coffee tastes! Lovelier than a thousand kisses, sweeter far than
    muscatel wine!
  who: Picander, set by J.S. Bach
  source: Schweigt stille, plaudert nicht — the "Coffee Cantata," BWV 211, c. 1735
  attribution: verified
  note: >-
    Bach wrote a comic opera about a young woman whose father tries to break her coffee
    habit. She refuses. The coffee-shop argument is three hundred years old.
  tags: [coffee, fun, weird]

- text: >-
    I think it must be a slow poison. I have been drinking it for eighty-five years and
    I am not dead yet.
  who: Voltaire
  source: told about him, not by him — no contemporary source exists
  attribution: disputed
  note: >-
    A great line and almost certainly invented after his death. Voltaire really did drink
    an enormous amount of coffee; he really didn't say this.
  tags: [coffee, fun]

- text: >-
    The discovery of a new dish does more for the happiness of mankind than the discovery
    of a new star.
  who: Jean Anthelme Brillat-Savarin
  source: Physiologie du Goût, 1825 — Aphorism IX
  attribution: verified
  tags: [cooking, making]

- text: "Eating is an agricultural act."
  who: Wendell Berry
  source: The Pleasures of Eating, 1989
  attribution: verified
  note: >-
    Berry's point is that eaters are participants in the food economy, not an audience
    for it. Which is roughly the thesis of this newsletter.
  tags: [making, consuming, local]

- text: >-
    The only real stumbling block is fear of failure. In cooking you've got to have a
    what-the-hell attitude.
  who: Julia Child
  source: widely quoted from her writing and interviews
  attribution: attributed
  tags: [cooking, courage]

- text: >-
    No one who cooks, cooks alone. Even at her most solitary, a cook in the kitchen is
    surrounded by generations of cooks past.
  who: Laurie Colwin
  source: Home Cooking, 1988
  attribution: verified
  tags: [cooking, making]

- text: "First we eat, then we do everything else."
  who: M.F.K. Fisher
  attribution: attributed
  note: Her most-quoted line, and no one can point to which book it's in.
  tags: [cooking, fun]

- text: >-
    We live in capitalism. Its power seems inescapable. So did the divine right of kings.
  who: Ursula K. Le Guin
  source: National Book Awards acceptance speech, 2014
  attribution: verified
  note: >-
    She was talking about publishing. It applies just as well to a monthly subscription
    for the service of deciding what you'll have for dinner.
  tags: [consuming, making]

- text: "The difference between screwing around and science is writing it down."
  who: Adam Savage
  attribution: verified
  note: >-
    The argument for the `rating:` field at the bottom of every recipe file in this repo.
    Fill it in and the system gets smarter. Don't, and it stays a guess.
  tags: [making, method]

- text: >-
    Have nothing in your houses that you do not know to be useful, or believe to be
    beautiful.
  who: William Morris
  source: The Beauty of Life (lecture), 1880
  attribution: verified
  tags: [making, consuming]

- text: "Let things taste of what they are."
  who: Richard Olney
  source: >-
    Olney's principle, adopted and made famous by Alice Waters and Chez Panisse
  attribution: verified
  note: >-
    The whole case for buying a tomato in August and not in February, in six words.
  tags: [cooking, seasonal]

- text: "Good food is very often, even most often, simple food."
  who: Anthony Bourdain
  source: Kitchen Confidential, 2000
  attribution: verified
  tags: [cooking]

- text: "Butter! Give me butter! Always butter!"
  who: Fernand Point
  source: Ma Gastronomie, 1969
  attribution: attributed
  note: Point ran La Pyramide and is more or less the father of modern French cooking.
  tags: [cooking, fun]

- text: "Anyone can cook. But only the fearless can be great."
  who: Auguste Gusteau
  source: Ratatouille, 2007 — a fictional chef in an animated film
  attribution: fiction
  note: Included without apology. It is the correct attitude.
  tags: [cooking, courage, fun]

- text: "A mathematician is a machine for turning coffee into theorems."
  who: Alfréd Rényi
  attribution: attributed
  note: >-
    Almost always credited to Paul Erdős, who quoted it constantly. Rényi appears to have
    said it first. Erdős took it seriously enough to run on amphetamines and espresso for
    decades.
  tags: [coffee, fun, weird]

- text: "The things you own end up owning you."
  who: Chuck Palahniuk
  source: Fight Club, 1996
  attribution: fiction
  tags: [consuming]

- text: >-
    Once you decide on your occupation, you must immerse yourself in your work. You have
    to fall in love with your work.
  who: Jiro Ono
  source: Jiro Dreams of Sushi, 2011
  attribution: verified
  tags: [making, craft]

- text: >-
    In 1746 Sweden banned coffee outright — along with the cups and saucers, which were
    confiscated. King Gustav III later tried to prove it was lethal by sentencing a pair
    of twin murderers to drink coffee and tea daily for life, with two doctors observing.
    The tea twin died first, at 83. Both doctors died before him. So did the king.
    The coffee twin outlived everyone.
  who: Sweden, 1746–1792
  attribution: history
  note: >-
    The trial is well documented in Swedish sources; some of the tidier details have
    grown in the retelling. The coffee bans were real, and there were five of them.
  tags: [coffee, weird, history]

- text: >-
    Søren Kierkegaard would fill a coffee cup to the brim with sugar — a small white
    mountain of it — then pour black coffee over the top until the sugar dissolved, and
    drink the result in one go.
  who: Søren Kierkegaard
  source: recorded by his contemporaries; recounted in Joakim Garff's biography
  attribution: history
  note: He did this daily. Nobody has ever explained it.
  tags: [coffee, weird]

- text: >-
    Beethoven counted out exactly sixty coffee beans per cup, every morning, by hand.
  who: Ludwig van Beethoven
  source: reported by his secretary Anton Schindler
  attribution: legend
  note: >-
    Schindler forged entries in Beethoven's conversation books and invented a good deal
    else, so treat this the way you'd treat any story with only one very unreliable
    witness. Sixty beans is roughly 11 grams, which would make a weak cup.
  tags: [coffee, weird, fun]

- text: >-
    In 1777 Frederick the Great issued a manifesto complaining that his subjects were
    drinking coffee instead of beer soup, that the money was leaving the country, and
    that his soldiers had been raised on beer and could not be relied upon to endure
    hardship on coffee.
  who: Frederick II of Prussia
  source: coffee manifesto, 1777
  attribution: history
  note: He also employed "coffee sniffers" to walk the streets detecting illegal roasting.
  tags: [coffee, weird, history]

- text: >-
    The story goes that an Ethiopian goatherd named Kaldi noticed his goats dancing after
    eating the red berries of a certain shrub, tried them himself, and became the first
    person to feel like this.
  who: Kaldi
  attribution: legend
  note: >-
    First written down around 1671, some eight centuries after coffee cultivation
    actually began. Almost certainly not true, and the best origin story any drink has.
  tags: [coffee, fun, legend]

- text: >-
    Coffee was banned in Mecca in 1511 on the grounds that it stimulated radical thinking
    and that coffee houses encouraged people to gather and talk politics.
  who: Khair Beg, governor of Mecca
  attribution: history
  note: >-
    The ban was overturned within a few years by the Sultan in Cairo. The objection was
    never really the drink; it was the room it created.
  tags: [coffee, history, weird]

- text: >-
    Theodore Roosevelt's coffee cup, according to his son, was "more in the nature of a
    bathtub." He is said to have taken seven lumps of sugar in it.
  who: Theodore Roosevelt
  source: recalled by Theodore Roosevelt Jr.
  attribution: attributed
  tags: [coffee, fun]

- text: "Good cooking is the foundation of true happiness."
  who: Auguste Escoffier
  attribution: attributed
  tags: [cooking]

- text: >-
    A recipe has no soul. You as the cook must bring soul to the recipe.
  who: Thomas Keller
  attribution: attributed
  tags: [cooking, making]

- text: >-
    Beauty in craft is not put there by the maker. It arrives through use, and through
    the maker getting out of the way.
  who: Sōetsu Yanagi
  source: paraphrased from The Unknown Craftsman, 1972
  attribution: attributed
  note: Marked as a paraphrase because it is one — Yanagi's argument, not his sentence.
  tags: [making, craft]
```
