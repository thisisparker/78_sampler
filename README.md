# @78_sampler

This bot picks a random 78 record from the Great 78 Project, downloads the image and audio, and renders together a 140-second clip suitable for posting to Twitter. Then it uploads that video with a link to the tune. Follow it at [@78_sampler](https://twitter.com/78_sampler).

The `internetarchive` module required by this script also provides a command line interface that can be used to generate the `georgeblood.txt` file. The [George Blood collection at the Internet Archive](https://archive.org/details/georgeblood) is continually being expanded, so I run the following command on occasion:

```
ia search collection:georgeblood --itemlist > georgeblood.txt
```

Note that the collection currently contains over 300,000 items, so it is normal for that command to take some time to run.

The collection contains some items I never want the bot to tweet; I maintain a file called `exclude.txt` with a series of fixed strings that should not appear. I apply the filter with a simple grep:

```
grep -Fv -f exclude.txt georgeblood.txt
```
