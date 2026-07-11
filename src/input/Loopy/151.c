// Source: data/benchmarks/accelerating_invariant_generation/cav/19.c

int unknown1(){
    int x; return x;
}

int unknown2(){
    int x; return x;
}

int unknown3();
int unknown4();


/*@
  requires n >= 0;
  requires m >= 0;
  requires m <= n - 1;
*/
void loopy_151(int n, int m)
{
  int x=0; 
  int y;
  y = m;
  

  

  

  while(x<=n-1) {
    x++;
    if(x>=m+1) y++;
    else if(x > m) 
return;

    x = x;
  }
  if(x < n)
    
return;

  if(y >= n+1)
  {goto ERROR; { ERROR: {; 
//@ assert(\false);
}
}}
}