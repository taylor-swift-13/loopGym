// Source: data/benchmarks/accelerating_invariant_generation/cav/substring1.c

/*@
  requires k >= 0;
  requires k <= 100;
  requires from >= 0;
  requires from <= k;
*/
void loopy_159(int from, int to, int k) {
int i, j;












i = from;
j = 0;

while (i < k) {
i++;
j++;
}

if (j >= 101)
  goto ERROR;

return;

{ ERROR: {; 
//@ assert(\false);
}
}

}
