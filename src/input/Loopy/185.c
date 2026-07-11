// Source: data/benchmarks/accelerating_invariant_generation/dagger/substring1.c

/*@
  requires k >= 0;
  requires k <= 100;
  requires from >= 0;
  requires from <= k;
*/
void loopy_185(int from, int to, int k) {
int i, j;












i = from;
j = 0;

while (i < k) {
i++;
j++;
}

{;
//@ assert(j <= 100);
}

}
